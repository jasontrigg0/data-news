import json
import collections
import copy
import csv
import math
import glob
from bs4 import BeautifulSoup

PRIORITY_POSITIONS = ["QB", "RB", "WR", "TE"]
FLEX_POSITIONS = ["RB","WR","TE"]
YEAR = 2026


CUSTOM_POSITION_SLOTS = {}

CUSTOM_SCORING = {}

JT_LEAGUE = False
if JT_LEAGUE:
    CUSTOM_POSITION_SLOTS["Flex"] = 2
    CUSTOM_SCORING["pass_td"] = 6


#pull fantasypros, espn rankings, yahoo rankings
#and place in data/{YEAR}

#fantasypros projections can be downloaded position by position here
#https://www.fantasypros.com/nfl/projections/qb.php?week=draft
#adjust columns YDS, TDS to PASS_YDS, PASS_TDS, REC_YDS, REC_TDS, RUSH_YDS, RUSH_TDS
#used in load_ffpros_projections()

#pull yahoo pre-season rankings as described here:
#https://www.reddit.com/r/fantasyfootball/comments/wljadj/where_can_you_find_yahoos_draft_ranking_listed_out/
#https://football.fantasysports.yahoo.com/f1/792196/players?status=ALL&eteam=ALL&fteam=NONE&pos=O&cut_type=9&stat1=S_S_2025&myteam=0&sort=OR&sdir=1&count=0
#curl or download that url > /tmp/yahoo_00.html
#then set count=25 > /tmp/yahoo_25.html
#count=50 > /tmp/yahoo_50.html
#etc through count=175 > /tmp/yahoo_175.html
#then run
#process_yahoo_html()

#pull espn rankings from here:
#curl 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leaguedefaults/1?view=kona_player_info&platformVersion=96e7cdc122a61e6c778b4087703c10d123d0565d'

def pick_number_to_team(pick_number, team_cnt):
    offset = pick_number % (2*team_cnt)
    if offset < team_cnt:
        return offset
    else:
        return 2*team_cnt - 1 - offset

def get_pick_num(team_cnt, draft_pos, rnd):
    #rnd zero-indexed
    if rnd % 2 == 0:
        return (rnd * team_cnt) + draft_pos
    else:
        return (rnd * team_cnt) + team_cnt - draft_pos - 1

class FantasyFootballDraft():
    def __init__(self, team_cnt, position_slots, draft_pos_to_strategy, all_players):
        self.team_cnt = team_cnt
        self.round_cnt = round(150 / team_cnt)
        self.teams = {}
        for i in range(self.team_cnt):
            self.teams[i] = {
                "status": FantasyDraftStatus(position_slots),
                "strategy": draft_pos_to_strategy[i]
            }
            
        #player options
        self.remaining_players = all_players
        self.draft_results = []
    def simulate_draft(self):
        for pick_num in range(self.round_cnt * self.team_cnt):
            draft_pos = pick_number_to_team(pick_num, self.team_cnt)
            pick = self.teams[draft_pos]["strategy"].make_pick(self.teams[draft_pos]["status"],self.remaining_players)
            self.teams[draft_pos]["status"].add_pick(pick)
            self.remaining_players = [x for x in self.remaining_players if x["name"] != pick["name"]]
            self.draft_results.append({
                "pick_num": pick_num,
                "team": draft_pos,
                "pick": pick,
            })


class FantasyDraftSimpleStrategy():
    def __init__(self):
        pass
    def make_pick(self, draft_status, remaining):
        best_pick = None
        best_val = 0
        all_available = draft_status.available_positions()
        priority_available = [x for x in all_available if x in PRIORITY_POSITIONS]
        for pick in remaining:
            pos = pick["position"]
            if not pos in PRIORITY_POSITIONS: continue
            if priority_available:
                if pos in priority_available:
                    return pick
            else:
                #already filled starter slots, pick any priority player
                return pick
            
#includes a value for every possible draft scenario
#remaining_slots -> (pick, remaining_value)
class FantasyDraftCompleteStrategy():
    def __init__(self, team_cnt, draft_pos, position_slots, estimated_draft_order = None):
        self.draft_status_by_hash = {}
        
        self.team_cnt = team_cnt
        self.position_slots = position_slots
        
        self.draft_pos = draft_pos
        if estimated_draft_order:
            all_players = estimated_draft_order
        else:
            all_players = load_espn_draft_order()
        self.players = [x for x in all_players if x["position"] in PRIORITY_POSITIONS]
        for i,x in enumerate(self.players):
            x["pick_num"] = i
    def make_pick(self, draft_status, remaining):
        best_pick = None
        best_val = 0

        #outside of the strategy, can pick whatever
        if not str(draft_status) in self.draft_status_by_hash:
            return remaining[0]
        
        our_draft_status = self.draft_status_by_hash[str(draft_status)]
        pos_to_remaining_val = our_draft_status.pos_to_remaining_val
        if not pos_to_remaining_val:
            #already filled priority slots, can pick whatever
            return remaining[0]
        for pos in pos_to_remaining_val:
            remaining_val = pos_to_remaining_val[pos]
            pick = sorted([x for x in remaining if x["position"] == pos], key = lambda x: x["value"], reverse=True)[0]
            total_val = pick["value"] + remaining_val

            #if two picks have the same value choose the one with the lower pick_num
            pick_num = pick["pick_num"]
            best_pick_num = best_pick["pick_num"] if best_pick else math.inf
            
            if (total_val, -pick_num) > (best_val, -best_pick_num):
                best_pick = pick
                best_val = total_val
        return best_pick
    def calc_forward_step(self, draft_status, pos):
        pick = self.get_best_available(draft_status, pos)
        new_status = copy.deepcopy(draft_status)
        new_status.add_pick(pick)
        new_val = new_status.current_value()
        new_pick_nums = [-x["pick_num"] for x in new_status.picks]
        
        curr_val = 0
        curr_pick_nums = -math.inf
        if str(new_status) in self.draft_status_by_hash:
            curr_val = self.draft_status_by_hash[str(new_status)].current_value()
            picks = self.draft_status_by_hash[str(new_status)].picks
            curr_pick_nums = [-x["pick_num"] for x in picks]

        if (new_val, new_pick_nums) > (curr_val, curr_pick_nums):
            self.draft_status_by_hash[str(new_status)] = new_status
    def calc_backward_step(self, draft_status, pos):
        pick = self.get_best_available(draft_status, pos)
        draft_status.next_pick = pick
        new_status = copy.deepcopy(draft_status)
        new_status.add_pick(pick)
        remaining_val = self.draft_status_by_hash[str(new_status)].remaining_val
        draft_status.set_pick_val(pick, remaining_val)
    def get_rnd_cnt(self):
        return sum([self.position_slots[x] for x in self.position_slots if x in PRIORITY_POSITIONS or x == "Flex"])
    def calculate(self):
        self.run_forward_pass()
        self.run_backward_pass()
        self.add_targets()
    def run_forward_pass(self):
        initial_status = FantasyDraftStatus(self.position_slots, [])
        self.draft_status_by_hash[str(initial_status)] = initial_status

        for rnd in range(self.get_rnd_cnt()):
            all_draft_statuses = [x for x in self.draft_status_by_hash.values() if len(x.picks) == rnd]
            for draft_status in all_draft_statuses:
                for pos in draft_status.available_positions():
                    if pos not in PRIORITY_POSITIONS: continue
                    self.calc_forward_step(draft_status, pos)
    def run_backward_pass(self):
        complete_draft_statuses = [x for x in self.draft_status_by_hash.values() if len(x.picks) == self.get_rnd_cnt()]
        for status in complete_draft_statuses:
            status.set_remaining_val(0)
            
        for rnd in list(range(self.get_rnd_cnt()))[::-1]:
            all_draft_statuses = [x for x in self.draft_status_by_hash.values() if len(x.picks) == rnd]
            for draft_status in all_draft_statuses:
                for pos in draft_status.available_positions():
                    if pos not in PRIORITY_POSITIONS: continue
                    self.calc_backward_step(draft_status, pos)
            
    def add_targets(self):
        for hash_ in self.draft_status_by_hash:
            status = self.draft_status_by_hash[hash_]
            rnd = len(status.picks)
            pick_num = get_pick_num(self.team_cnt, self.draft_pos, rnd)
            options = sorted([x for x in self.players if x["pick_num"] >= pick_num-10 and x["pick_num"] >= pick_num/2 and x["position"] in status.pos_to_remaining_val], key = lambda x: x["value"] + status.pos_to_remaining_val[x["position"]], reverse=True)[:10]
            status.targets = options
    def get_best_available(self, draft_status, pos):
        already_picked = [x["name"] for x in draft_status.picks]
        rnd = len(already_picked)
        pick_num = get_pick_num(self.team_cnt, self.draft_pos, rnd)
        options = sorted([x for x in self.players if x["position"] == pos and x["pick_num"] >= pick_num and x["name"] not in already_picked], key = lambda x: x["value"], reverse=True)
        if not options:
            print(self.players)
            print(pick_num)
            print(draft_status, pos)
            raise
        return options[0]
            
class FantasyDraftStatus():
    def __init__(self, position_slots, picks = None):
        self.position_slots = position_slots
        self.picks = picks or []
        
        self.next_pick = None
        self.targets = None
        
        #value estimates
        self.remaining_val = None
        self.pos_to_remaining_val = {}
    def set_remaining_val(self, remaining_value):
        self.remaining_val = remaining_value
    def set_pick_val(self, pick, remaining_value):
        pos = pick["position"]
        self.pos_to_remaining_val[pos] = remaining_value
        pick_remaining_val = pick["value"] + remaining_value
        self.remaining_val = max(self.remaining_val or 0, pick_remaining_val)
    def total_value(self):
        return self.current_value() + self.remaining_val
    def current_value(self):
        return sum(pick["value"] for pick in self.picks)
    def get_picks_by_pos(self):
        picks_by_pos = {}
        for p in self.picks:
            picks_by_pos[p["position"]] = picks_by_pos.setdefault(p["position"],0) + 1
        return picks_by_pos
    def available_positions(self):
        picks_by_pos = self.get_picks_by_pos()
        
        available = set([])
        #have we used up flex positions?
        flex_cnt = 0

        for pos in FLEX_POSITIONS:
            flex_cnt += max(picks_by_pos.get(pos,0) - self.position_slots.get(pos,0),0)
        if self.position_slots.get("Flex",0) > flex_cnt:
            for pos in FLEX_POSITIONS:
                available.add(pos)
        #non flex positions
        for pos in self.position_slots:
            if pos == "Flex": continue
            if self.position_slots.get(pos,0) > picks_by_pos.get(pos,0):
                available.add(pos)
        return list(available)
    def add_pick(self, pick):
        self.picks.append(pick)
    def __len__(self):
        return len(self.picks)
    def __str__(self):
        return json.dumps(self.get_picks_by_pos(), sort_keys=True)
    def __deepcopy__(self, memo):
        new_instance = FantasyDraftStatus(copy.deepcopy(self.position_slots), copy.deepcopy(self.picks))
        return new_instance

def load_ffpros_projections(league, ppr=0):
    ffpros_scoring = {
        "pass_yds": 0.04,
        "pass_tds": 4,
        "ints": -1,
        "rush_yds": 0.1,
        "rush_tds": 6,
        "rec": 0,
        "rec_yds": 0.1,
        "rec_tds": 6,
        "fumbles_lost": -2
    }

    league_scoring = {**ffpros_scoring}
    
    #yahoo vs espn vary in interception scoring
    #yahoo = -1, espn = -2
    league_scoring["rec"] = ppr
    
    if league == "espn":
        league_scoring["ints"] = -2
    elif league == "yahoo":
        league_scoring["ints"] = -1
    else:
        raise

    league_scoring = {**league_scoring, **CUSTOM_SCORING}
    
    player_to_projection = {}
    for pos in ["QB","RB","WR","TE","K","DST"]:
        reader = csv.DictReader(open(f"data/{YEAR}/FantasyPros_Fantasy_Football_Projections_{pos}.csv"))
        for row in reader:
            if not row["Player"].strip(): continue
            proj = float(row["FPTS"])
            fields = {
                "PASS_YDS": "pass_yds",
                "PASS_TDS": "pass_tds",
                "INTS": "ints",
                "REC": "rec",
                "REC_YDS": "rec_yds",
                "REC_TDS": "rec_tds",
                "RUSH_YDS": "rush_yds",
                "RUSH_TDS": "rush_tds",
                "FL": "fumbles_lost",
            }
            for x in fields:
                if x not in row: continue
                proj += float(row[x]) * (league_scoring[fields[x]] - ffpros_scoring[fields[x]])
            
            #error if there are duplicate names
            if row["Player"] in player_to_projection:
                print("Duplicate player found: " + row["Player"])
                raise
            player_to_projection[row["Player"]] = round(proj,1)

    unrated = [] #"Keenan Allen", "Amari Cooper", "Justin Tucker", "Gabe Davis", "Cam Akers", "Xavier Restrepo"]
    for player in unrated:
        if player not in player_to_projection:
            player_to_projection[player] = 0
    
    return player_to_projection

def process_yahoo_html():
    #see instructions at the top of file for downloading / curling yahoo data
    players = []
    for path in glob.glob("/tmp/yahoo*.html"):
        with open(path) as f:
            data = json.loads(f.read())
            soup = BeautifulSoup(data["content"], "html.parser")
        for row in soup.select("div#players-table tbody tr"):
            rank = row.select("td")[7].text
            pos = row.select("td span.D-b")[0].text.strip().split()[-1].strip()
            name = row.select("a.playernote")[0].text
            players.append([int(rank), name, pos])

    players.sort()
    with open(f"data/{YEAR}/Yahoo-Rankings.csv","w") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(["Rank","Player Name","Position"])
        for r in players:
            writer.writerow([str(x) for x in r])

def load_yahoo_order(ppr):
    #pulled from here, check back once actual draft opens up
    #https://sports.yahoo.com/fantasy/article/fantasy-football-rankings-2025-144031309.html
    reader = csv.DictReader(open(f"data/{YEAR}/Yahoo-Rankings.csv"))
    rankings = [row for row in reader]
    player_to_projection = load_ffpros_projections("yahoo", ppr)

    name_mappings = {
        "Patrick Mahomes": "Patrick Mahomes II",
        "Brian Robinson": "Brian Robinson Jr.",
        "Oronde Gadsden": "Oronde Gadsden II",
    }
    
    draft_order = []
    for row in rankings:
        player_name = row["Player Name"]
        player_name = name_mappings.get(player_name,player_name)
        if not player_name in player_to_projection:
            print("Couldn't find player in FantasyPros projections, add to name_mappings: " + player_name)
            raise
        proj_total = player_to_projection[player_name]
        draft_order.append({
            "name": player_name,
            "position": row["Position"].replace("DST","D/ST"),
            "value": proj_total,
        })
    return draft_order
        
def load_espn_order(ppr):
    draft_order = []
    rankings = json.loads(open(f"data/{YEAR}/espn.json").read())["players"]

    if ppr == 0:
        rankings.sort(key = lambda x: x["player"]["draftRanksByRankType"]["STANDARD"]["rank"])
    else:
        rankings.sort(key = lambda x: x["player"]["draftRanksByRankType"]["PPR"]["rank"])

    rankings = rankings[:200]

    name_mappings = {
        "Patrick Mahomes": "Patrick Mahomes II",
        "Hollywood Brown": "Marquise Brown",
        "Texans D/ST": "Houston Texans",
        "Eagles D/ST": 'Philadelphia Eagles',
        "Cowboys D/ST": 'Dallas Cowboys',
        "Bills D/ST": 'Buffalo Bills',
        "Giants D/ST": 'New York Giants',
        "Texans D/ST": 'Houston Texans',
        "Packers D/ST": 'Green Bay Packers',
        "Ravens D/ST": 'Baltimore Ravens',
        "Broncos D/ST": 'Denver Broncos',
        "Steelers D/ST": 'Pittsburgh Steelers',
        "Lions D/ST": 'Detroit Lions',
        "Commanders D/ST": 'Washington Commanders',
        "Bears D/ST": 'Chicago Bears',
        "Chargers D/ST": 'Los Angeles Chargers',
        "49ers D/ST": 'San Francisco 49ers',
        "Rams D/ST": 'Los Angeles Rams',
        "Cardinals D/ST": 'Arizona Cardinals',
        "Vikings D/ST": 'Minnesota Vikings',
        "Seahawks D/ST": 'Seattle Seahawks',
        "Buccaneers D/ST": 'Tampa Bay Buccaneers',
        "Colts D/ST": 'Indianapolis Colts',
        "Chiefs D/ST": 'Kansas City Chiefs',
        "Browns D/ST": 'Cleveland Browns',
        "Jets D/ST": 'New York Jets',
        "Bengals D/ST": 'Cincinnati Bengals',
        "Falcons D/ST": 'Atlanta Falcons',
        "Titans D/ST": 'Tennessee Titans',
        "Dolphins D/ST": 'Miami Dolphins',
        "Raiders D/ST": 'Las Vegas Raiders',
        "Saints D/ST": 'New Orleans Saints',
        "Jaguars D/ST": 'Jacksonville Jaguars',
        "Patriots D/ST": 'New England Patriots',
        "Panthers D/ST": 'Carolina Panthers',
    }
    
    player_to_projection = load_ffpros_projections("espn", ppr)
    
    for i, player in enumerate(rankings):
        player_name = player["player"]["fullName"]
        player_name = name_mappings.get(player_name,player_name)
        position_id = player["player"]["defaultPositionId"]
        position = {
            1: "QB",
            2: "RB",
            3: "WR",
            4: "TE",
            5: "K",
            16: "D/ST",
        }[position_id]

        if not player_name in player_to_projection:
            print("Couldn't find player in FantasyPros projections, add to name_mappings: " + player_name)
            raise
        proj_total = player_to_projection[player_name]

        draft_order.append({
            "name": player_name,
            "position": position,
            "value": proj_total,
        })
    return draft_order

def load_players(league, ppr):
    if league == "espn":
        return load_espn_order(ppr)
    elif league == "yahoo":
        return load_yahoo_order(ppr)
    else:
        raise

def get_baseline_order(team_cnt, position_slots, all_players):
    draft_pos_to_naive = {i:FantasyDraftSimpleStrategy() for i in range(team_cnt)}
    draft = FantasyFootballDraft(team_cnt, position_slots, draft_pos_to_naive, all_players)
    draft.simulate_draft()
    estimated_order = [{**x["pick"], "pick_num":x["pick_num"]} for x in draft.draft_results]
    return estimated_order

def get_best_strategy(position_slots, team_cnt, all_players):
    baseline_order = get_baseline_order(team_cnt, position_slots, all_players)
    
    draft_pos_to_strategy = {}
    for i in range(team_cnt):
        strat = FantasyDraftCompleteStrategy(team_cnt, i, position_slots, baseline_order)
        strat.calculate()
        draft_pos_to_strategy[i] = strat
    
    draft = FantasyFootballDraft(team_cnt, position_slots, draft_pos_to_strategy, baseline_order)
    draft.simulate_draft()
    #estimated_order = [{**x["pick"], "pick_num":x["pick_num"]} for x in draft.draft_results]

    player_to_baseline = {x["name"]:i for i,x in enumerate(baseline_order)}
    
    info = {
        "player_ranking": [{"pick_num": x["pick_num"] + 1, "name": x["pick"]["name"], "pos": x["pick"]["position"], "gap": player_to_baseline[x["pick"]["name"]] - x["pick_num"]} for x in draft.draft_results],
        "draft_strategies": {},
    }
        
    for i in range(team_cnt):
        # print("---")
        # print("---")
        # print("---")
        # print("---")
        # for rnd in range(draft_pos_to_strategy[i].get_rnd_cnt()):
        for rnd in [draft_pos_to_strategy[i].get_rnd_cnt()-1]:
            best_val = 0
            best_status = None
            for x in draft_pos_to_strategy[i].draft_status_by_hash:
                status = draft_pos_to_strategy[i].draft_status_by_hash[x]
                if sum(status.get_picks_by_pos().values()) != rnd+1:
                    continue
                if status.total_value() > best_val:
                    best_val = status.total_value()
                    best_status = status
            info["draft_strategies"][i+1] = {
                "total_value": round(best_val,1),
                "sample_picks": best_status.picks
            }
            # print(best_val, best_status.picks)
            # print(best_status.next_pick)
            # print(best_status.targets)
    return info

    
def get_equilibrium_draft(position_slots, team_cnt, all_players):
    baseline_order = get_baseline_order(team_cnt, position_slots, all_players)

    estimated_order = baseline_order
    for _ in range(100):
        draft_pos_to_strategy = {}
        for i in range(team_cnt):
            strat = FantasyDraftCompleteStrategy(team_cnt, i, position_slots, estimated_order)
            strat.calculate()
            draft_pos_to_strategy[i] = strat
        draft = FantasyFootballDraft(team_cnt, position_slots, draft_pos_to_strategy, estimated_order)
        draft.simulate_draft()
        estimated_order = [{**x["pick"], "pick_num":x["pick_num"]} for x in draft.draft_results]
    for x in draft.draft_results[:100]:
        print(x)


if __name__ == "__main__":
    #process_yahoo_html()
    #load_yahoo_order(0)
    #load_espn_order(0.5)
    
    position_slots = {
        "QB": 1,
        "RB": 2,
        "WR": 2,
        "TE": 1,
        "Flex": 1,
        "D/ST": 1,
        "K": 1,
    }

    position_slots = {**position_slots, **CUSTOM_POSITION_SLOTS}
    
    output = {}
    for team_cnt in [8,10,12]:
        for league in ["espn", "yahoo"]:
            for ppr in [0, 0.5, 1]:
                print(team_cnt, league, ppr)
                key = "|".join([str(team_cnt),str(ppr),league])
                all_players = load_players(league, ppr)
                info = get_best_strategy(position_slots, team_cnt, all_players)
                #get_equilibrium_draft(position_slots, team_cnt, all_players)
                output[key] = info

    json_file_path = f'../../web-app/src/assets/data/ff_draft_stats.json'
    with open(json_file_path, mode='w', encoding='utf-8') as jsonfile:
        json.dump(output, jsonfile, indent=4)

