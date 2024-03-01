
# To Run

python battery/sims.py rec_def.json

 #

# Structure of rec_def.json
```
[{
  "system_size_kwh": 15,
  "system_size_kw": 5,
  "site_export_limit_kw": 5,
  "rec_id": 666,
  "ttl": 60
},
{
  "system_size_kwh": 15,
  "system_size_kw": 5,
  "site_export_limit_kw": 5,
  "rec_id": 667,
  "ttl": 65
}]
```
  

**NOTE**
To provide different intervals to different batteries/recs/simulatoin introduce "interval" (between 1 to 59 in minutes) param in the above def

  
# Simulation logic

On execution app will create as many simulators as there are number of unique rec_id present in the rec_def.json

Server ports will start from 8050 and will go on by increment of 1
  
# APIs

## POST a schedule

```
curl -X POST localhost:8055/sims --data '{"start_ts": "2023-02-28T03:00:00Z", "end_ts": "2023-02-28T03:00:00Z", "target_soc": 100, "state": "charge"}'
```
**NOTE**
1. Use timestamp with today's date.
 2. state could be charge/discharge/idle
 3. Do not use idle state in the POST request json , it will only be used to define battery at rest condition

### sample output
```
{"message": "Schedule created", "data": [{"start_ts": "2023-03-01T13:00:00Z", "end_ts": "2024-03-01T16:00:00Z", "target_soc": 10, "state": "discharge"}, {"start_ts": "2024-03-01T03:00:00Z", "end_ts": "2024-03-01T06:00:00Z", "target_soc": 100, "state": "charge"}]}
```
  
## GET the simulation data
```
curl -X GET localhost:8055/sims
```
### sample output
```
{"rec_id": 671, "start_ts": "2024-03-01T03:45:00Z", "end_ts": "2024-03-01T04:00:00Z", "state": "idle", "soc": 90.0, "kwh": 1350.0}
```
