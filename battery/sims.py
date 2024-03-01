import falcon
from wsgiref import simple_server
import json
from datetime import datetime, timedelta
import threading
import sys


# schedule storage
rec_schedule_store = 'rec_schedule.txt'

# unit of interval at which charge or discharge will be calculated
interval = 15


class Ess:
    def __init__(self, interval, rec_id, system_size_kwh):
        self.rec_id = rec_id
        self.initial_soc = 60
        self.schedule = []
        # percent of discharge per interval
        self.std_discharge_rate = 0
        self.interval = interval
        self.system_size_kwh = system_size_kwh
        self.soc_at_interval = []

    def parse_timestamp(self, ts):
        return (datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ'))

    def add_schedule(self, new_schedule):
        """
        rec_schedule = [
            {
                'start_ts': '2024-03-01T17:00:00Z',
                'end_ts': '2024-03-01T19:00:00Z',
                'target_soc': 80,
                'state': 'charge'
            },
            {
                'start_ts': '2024-03-01T21:00:00Z',
                'end_ts': '2024-03-01T22:00:00Z',
                'target_soc': 50,
                'state': 'discharge'
            },
            {
                'start_ts': '2024-03-01T01:00:00Z',
                'end_ts': '2024-03-01T03:00:00Z',
                'target_soc': 90,
                'state': 'charge'
            }
        ]
        """
        # self.schedule = rec_schedule
        self.schedule.append(new_schedule)
        self.schedule = sorted(self.schedule, key=lambda x: x['start_ts'])

        print('===========My Schedule is===============', self.schedule)

        self.update_soc_at_interval()

    def create_initial_soc_at_interval(self):
        current_datetime = datetime.now()
        start_of_day = current_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        interval_start = start_of_day

        print('==================Woring on init soc list============')

        while interval_start < start_of_day + timedelta(days=1):
            interval_end = interval_start + timedelta(minutes=self.interval)
            self.soc_at_interval.append({
                'rec_id': self.rec_id,
                'start_ts': interval_start.isoformat() + 'Z',
                'end_ts': interval_end.isoformat() + 'Z',
                'state': 'idle',
                'soc': self.initial_soc,
                'kwh': self.initial_soc * self.system_size_kwh
            })
            interval_start = interval_end

    def update_soc_at_interval(self):
        prev_soc = self.initial_soc
        for schedule in self.schedule:
            print('=================working on schedule===========', schedule)

            schedule_start = self.parse_timestamp(schedule['start_ts'])
            schedule_end = self.parse_timestamp(schedule['end_ts'])
            rate = self.get_rate(schedule, prev_soc)
            print('================schedule rate is==============', rate)
            for interval in self.soc_at_interval:

                interval_start_ts = self.parse_timestamp(interval['start_ts'])
                interval_end_ts = self.parse_timestamp(interval['end_ts'])

                if interval_start_ts >= schedule_start and interval_end_ts <= schedule_end:
                    state = schedule['state']
                    if state == 'charge':
                        if prev_soc >= schedule['target_soc']:
                            print("Though in schedule interval not charging due to initial soc")
                            soc = prev_soc
                        else:
                            soc = min(prev_soc + rate, 100)
                    else:
                        if prev_soc <= schedule['target_soc']:
                            print("Though in schedule interval not discharging due to initial soc")
                            soc = prev_soc
                        else:
                            soc = max(prev_soc + rate, 0)
                    print("===========************calculated an interval", state, soc, interval['start_ts'], interval['end_ts'])
                    interval['state'] = state
                    interval['soc'] = soc
                    interval['kwh'] = soc * self.system_size_kwh
                    prev_soc = soc
                if interval_start_ts >= schedule_end:
                    interval['soc'] = prev_soc
                    interval['kwh'] = prev_soc * self.system_size_kwh

        print('=================finished all schedules, socs are===========', self.soc_at_interval)

    def get_rate(self, schedule, initial_soc):
        start_ts = self.parse_timestamp(schedule['start_ts'])
        end_ts = self.parse_timestamp(schedule['end_ts'])
        total_duration_minutes = (end_ts - start_ts).total_seconds() / 60
        total_intervals = int(total_duration_minutes // interval)
        total_soc_change = schedule['target_soc'] - initial_soc
        rate_per_interval = total_soc_change / total_intervals if total_intervals else 0
        return rate_per_interval

    def on_post(self, req, resp):
        """Handles POST requests to add a schedule."""
        try:
            # Read the JSON data from the request
            raw_json = req.bounded_stream.read()
            new_schedule = json.loads(raw_json)

            self.add_schedule(new_schedule)

            # Set the status code and body of the response
            resp.status = falcon.HTTP_201  # Resource created
            resp.body = json.dumps({'message': 'Schedule created', 'data': self.schedule})
        except json.JSONDecodeError:
            resp.status = falcon.HTTP_400  # Bad request
            resp.body = json.dumps({'message': 'Invalid JSON'})

    def get_interval_number_from_start_of_day(self):
        current_ts = datetime.now()
        start_of_day_dt = current_ts.replace(hour=0, minute=0, second=0, microsecond=0)
        delta_minutes = (current_ts - start_of_day_dt).total_seconds() / 60
        interval_number = int(delta_minutes // self.interval)
        return interval_number

    def on_get(self, req, resp):
        """Handles GET requests to report server status."""
        interval_number = self.get_interval_number_from_start_of_day()
        print("============Accessing status on interval===============", interval_number)
        resp.status = falcon.HTTP_200  # OK
        resp.body = json.dumps(self.soc_at_interval[interval_number])


def start_simulator(ess_id, interval, system_size_kwh, port):
    app = falcon.App()
    ess_resource = Ess(interval, ess_id, system_size_kwh)
    ess_resource.create_initial_soc_at_interval()
    app.add_route('/sims', ess_resource)
    httpd = simple_server.make_server('127.0.0.1', port, app)
    print(f"Starting server {ess_id} on port {port}")
    httpd.serve_forever()


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_rec_def_json_file>")
        sys.exit(1)

    file_path = sys.argv[1]

    with open(file_path, 'r') as file:
        data = json.load(file)

    unique_records = []
    seen_rec_ids = set()

    for item in data:
        rec_id = item["rec_id"]
        system_size_kwh = item["system_size_kwh"]
        interval = item.get("interval", 15)
        # Check if the rec_id has not been processed before
        if rec_id not in seen_rec_ids:
            seen_rec_ids.add(rec_id)
            unique_records.append((rec_id, interval, system_size_kwh))

    starting_port = 8050
    threads = []
    for rec_id, interval, system_size_kwh in unique_records:
        t = threading.Thread(target=start_simulator, args=(rec_id, interval, system_size_kwh, starting_port))
        t.start()
        threads.append(t)
        starting_port += 1

    # Join threads to keep the main thread running
    for thread in threads:
        thread.join()
    # Create the Falcon application object
    app = falcon.App()

    for thread in threads:
        thread.join()
