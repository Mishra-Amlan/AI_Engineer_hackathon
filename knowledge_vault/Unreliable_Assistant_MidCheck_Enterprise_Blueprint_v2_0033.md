---
id: Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2#0033
domain: engineering
risk_tier: 1
version: v1
---
# B. Apache JMeter Distributed Controller-Worker Plan (`load_tests/jmeter_50k_plan.jmx`)

Distributed Thread Group Topology: Configure 1 JMeter Controller orchestrating 10 Distributed Worker injectors (`5,000 threads/worker = 50,000 total VUs`, `Ramp-Up = 180s`, `Loop Count = Infinite` over `600s` duration) in non-GUI CLI mode: `jmeter -n -t jmeter_50k_plan.jmx -R worker1..worker10 -l results_50k.jtl -e -o dashboard_50k/`. Assertions & Telemetry Listeners: Attach `Duration Assertion (600 ms)`, `JSONPath Assertion ($.faithfulness >= 0.92)`, `Constant Throughput Timer`, and `Backend Listener (InfluxDB/Prometheus)` to validate JDBC/SQLite persistence and HTTP endpoints simultaneously.

## Related
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0032]]
- [[Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2_0034]]
