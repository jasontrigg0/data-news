set -x

#news
cd news
python3 generate_news.py
cd ..

#approval ratings
cd approval_ratings
curl https://static.dwcdn.net/data/vknzT.csv?v=0 | sed 's/7\/31 - 7\/6, 2025/7\/31 - 8\/6, 2025/g' | sed 's/12\/13 - 12\/13, 2025/12\/15 - 12\/15, 2025/g' | sed 's/12\/20 - 12\/21, 2025/12\/22 - 12\/23, 2025/g' | sed 's/1\/23, 2026 - 1\/29, 2025/1\/23 - 1\/29, 2026/g' | sed 's/1\/31 - 2\/1, 2026/2\/2 - 2\/3, 2026/g' | sed 's/2\/21 - 2\/22, 2026/2\/23 - 2\/24, 2026/g' | sed 's/2\/28 - 2\/28, 2026/3\/2 - 3\/2, 2026/g' | sed 's/2\/28 - 3\/1, 2026/3\/2 - 3\/3, 2026/g' | sed 's/9\/28 - 9\/28, 2025/9\/29 - 9\/29, 2025/g' | sed 's/1\/24 - 1\/24, 2026/1\/26 - 1\/26, 2026/g' | sed 's/6\/27 - 6\/28, 2026/6\/26 - 6\/26, 2026/g' | sed 's/7\/11 - 7\/12, 2026/7\/10 - 7\/10, 2026/g' > polls.csv
python3 approval_polling.py
cd ..

#sports elos
cd sports_elos
python3 populate_data.py
cd ..

set +x

#cd ../../web-app
#npm run build
#npm run deploy
