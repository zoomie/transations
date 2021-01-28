import React, { useState, useEffect } from "react";
import "./App.css";
import "./Graph";
import Graph from "./Graph";
import Button from "./Button";

export default function App() {
  const [dis, setDis] = useState(<Button></Button>);
  // const url = "/api/transactions/test";
  const url = "/api/transactions";
  let fetchAns = async () => {
    let res = await fetch(url);
    res = await res.json();
    console.log(res.user_has_data);
    if (res.user_has_data === true) {
      setDis(<Graph data={res.transactions}></Graph>);
    }
  };
  useEffect(() => {
    fetchAns();
  }, []);
  return <div className="primary">{dis}</div>;
}
