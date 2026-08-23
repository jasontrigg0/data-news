import { useState } from 'react';
import modelData from './assets/data/models.json';
import evalData from './assets/data/evals.json';
import { Cell, Label, ScatterChart, Scatter, LabelList, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import { ToggleGroup } from './ToggleGroup';

const AILeaderboard = () => {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <>
    <div style={{"padding-left": "25px"}}>
      <div>Tracking the road to AGI. Underlying benchmarks <a href="https://docs.google.com/spreadsheets/d/1HqUzsuFN6Jb91zNMAz7bmqmt2wB8KCsR3gkBlHEzDro" style={{"text-decoration": "underline"}}>here</a>.
      </div>
    </div>
    <div className="max-w-1400 mx-auto mt-6 rounded-lg shadow-md overflow-hidden">
      {/* Tab Navigation */}
      <div className="flex border-b">
        {tabs.map((tab, index) => (
          <button
            key={index}
            className={`py-3 px-6 font-medium text-sm focus:outline-none ${
              activeTab === index
                ? 'text-blue-600 border-b-2 border-blue-600 bg-white'
                : 'text-gray-500 hover:text-blue-500 bg-gray-50'
            }`}
            onClick={() => setActiveTab(index)}
          >
            {tab.title}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-6 bg-white">
        {tabs.map((tab, index) => (
          <div key={index} className={activeTab === index ? 'block' : 'hidden'}>
            {tab.content}
          </div>
        ))}
      </div>
    </div>
    </>
  );
}

const PerformanceChart = ({xAxisVar, xAxisTicks, xAxisDomain, xAxisLabel}) => {
  const [cutoffTime, setCutoffTime] = useState(null);

  let data = modelData;
  if (cutoffTime) {
    data = modelData.filter(x => x.release_date < cutoffTime);
  }

  data = data.filter(x => !!x[xAxisVar]);

  const best = [data[0]["model"]];

  let currPrice = data[0][xAxisVar];
  let currRating = data[0]["rating"];
  for (let m of data) {
    if (m[xAxisVar] && m[xAxisVar] < currPrice) {
      best.push(m["model"]);
      currPrice = m[xAxisVar];
      currRating = m["rating"];
    } 
  }


  const CustomTooltip = (props) => {
    const { active, payload, value } = props;
    if (!active || !payload || payload.length === 0) return null;

    return (
      <div className="custom-tooltip" style={{ background: '#fff', padding: 8, border: '1px solid #ccc' }}>
	<p>{`Model: ${payload[0]["payload"]["model"]}`}</p>
	  <p>
	    Score: {payload[1].value}
	  </p>
	  <p>
	    Price: ${payload[0].value.toFixed(2)}/1M tokens
	  </p>
      </div>
    );
  };

  const CustomLabel = ({ x, y, value }) => {
    if (!best.includes(value)) return null;

    return (
      <text
	x={x + 3}
	y={y - 10}
	fontSize={11}
	fill="#333"
	textAnchor="middle"
	dominantBaseline="central"
      >
	{value}
      </text>
    );
  };

  const dateOptions = [
    {id: "20240101", label: "Jan 1, 2024"},
    {id: "20240701", label: "Jul 1, 2024"},
    {id: "20250101", label: "Jan 1, 2025"},
    {id: "20250701", label: "Jul 1, 2025"},
    {id: "20260101", label: "Jan 1, 2026"},
    {id: "20260701", label: "Jul 1, 2026"},
    {id: null, label: "Now"},
  ];

  return (
  <>
   <ToggleGroup title={"Price vs Performance (select a date)"} options={dateOptions} defaultOption={null} callback={setCutoffTime} center={true}/>
   <ResponsiveContainer width="100%" height="85%" minWidth="450px" minHeight="600px">
    <ScatterChart
      data={data}
      margin={{
	top: 5,
	right: 30,
	left: 20,
	bottom: 30
      }}
    >
      <XAxis
        type="number"
	dataKey={xAxisVar}
	domain={xAxisDomain}
	tick={{ fontSize: 12 }}
	scale="log"
	reversed={true}
	allowDataOverflow={true}
	ticks={xAxisTicks}
      >
        <Label value={xAxisLabel} offset={-15} position="insideBottom" />	
      </XAxis>
      <YAxis
        type="number"
        dataKey="rating"
	domain={[0, 100]}
	tick={{ fontSize: 12 }}
	allowDataOverflow={true}
	ticks={[0,20,40,60,80,100]}
      >
        <Label value="Score" offset={-15} position="insideLeft" />
      </YAxis>
      <Tooltip
        key={JSON.stringify(data)}
	content={<CustomTooltip/>}
      />
      <Scatter data={data}>
        <LabelList dataKey="model" content={<CustomLabel/>} />
        {data.map((entry, index) => (
          <Cell key={`cell-${index}`} fill={best.includes(entry.model) ? "#77DD77" : "#FF6961"} />
        ))}
      </Scatter>
    </ScatterChart>
    </ResponsiveContainer>
    </>
  );
}

const BestModelList = () => {
  const modelHeaders = [
    {
      key: "model",
      label: "Model"
    },
    {
      key: "release_date",
      label: "Release Date"
    },
    {
      key: "rating",
      label: "Rating"
    }
  ];

  return (<div>
    <table className="min-w-full divide-y divide-gray-200">
      <thead className="bg-gray-50">
	<tr>
	  {modelHeaders.map((column, j) => (
	    <th key={j} scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24">{column.label}</th>
	  ))}
	</tr>
      </thead>
      <tbody className="bg-white divide-y divide-gray-200">
	{modelData.map((row, i) => (
	  <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
	    {modelHeaders.map((column, j) => (
	       <td key={j} className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-500">{row[column.key]}</td>
	    ))}
	  </tr>
	))}
      </tbody>
    </table>
  </div>);
}

const tabs = [
  {
    title: "Road to AGI",
    content: (<iframe src='https://flo.uri.sh/visualisation/23770620/embed' title='Interactive or visual content' class='flourish-embed-iframe' frameborder='0' scrolling='no' style={{width:"100%",height:"600px"}} sandbox='allow-same-origin allow-forms allow-scripts allow-downloads allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation'></iframe>)
  },
  {
    title: "Best Models",
    content: (<BestModelList/>)
  },
  {
    title: "Token Price vs Performance",
    content: (<PerformanceChart xAxisVar="price" xAxisTicks={[100,30,10,3,1,0.3,0.1,0.05]} xAxisDomain={[0.05, 100]} xAxisLabel="Price in $/1M Tokens (3:1 input to output ratio)"/>)
  },
  {
    title: "AA Cost vs Performance",
    content: (<PerformanceChart xAxisVar="aa_cost" xAxisTicks={[10000,3000,1000,300,100,30,10]} xAxisDomain={[10, 10000]} xAxisLabel="Artificial Analysis Cost in dollars"/>)
  },
];

export default AILeaderboard;
