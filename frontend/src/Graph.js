import React, { PureComponent } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

export default function Graph(params) {
  return (
    <AreaChart
      width={500}
      height={400}
      data={params.data}
      margin={{
        top: 10,
        right: 30,
        left: 0,
        bottom: 0,
      }}
    >
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey="timestamp" />
      <YAxis />
      <Tooltip />
      <Area type="monotone" dataKey="amount" stroke="#8884d8" fill="#8884d8" />
    </AreaChart>
  );
}
