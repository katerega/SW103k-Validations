Location	Purpose
/opt/swk103/	Executables and application files
/etc/swk103/	Configuration
/var/lib/swk103/	Persistent data
/var/log/swk103/	Application logs
/var/lib/swk103/evidence/	Validation evidence

step2 run this
VPS2 receiver server

cd SW103K-Eric-Validation

sudo ./VPS2/run_receiver.sh

Check Linux architecture and dependencies.
Verify license service if required.
Start the SW103K receiver.
Verify TCP 10300 is listening.
Display receiver readiness.

sudo ss -lntp | grep 10300

ONSERVER2 ie
sudo ss -lntp | grep 10300


VPS 1 — Sender
cd SW103K-Eric-Validation

./VPS1/01_prepare_source.sh


Then:
./VPS1/03_run_client.sh <VPS2_PUBLIC_IP>


The client should:
1. Verify the source file.
2. Calculate its SHA-256.
3. Connect to VPS 2.
4. Initiate SW103K transfer.
5. Record transmitted protocol bytes.
6. Record transfer duration.
7. Obtain receiver confirmation.
8. Produce a PASS/FAIL report.





The objective is one command on VPS 2, one command on VPS 1, and independently reproducible validation evidence







VPS2 — Receiver
- run_receiver.sh: starts the actual SW103K receiver.
- 02_collect_receiver.sh: collects received data and logs.
- Listens on TCP port 10300 if that is the confirmed protocol configuration.

VPS1 — Sender
- 01_prepare_source.sh: creates and hashes the source file.
- 03_run_client.sh: initiates the transfer using the actual SW103K client.
- eric_test_client.py: only if the existing implementation requires a Python client.

Evidence and verification
- Baseline TCP transfer.
- SW103K transfer.
- Network byte measurements.
- Actual receiver disk-storage measurements.
- SHA-256 integrity verification.
- Logs, timestamps and test configuration.


Testing sequence
Do not attempt the 10 GB test yet.
1. Confirm the actual sender and receiver implementation.
2. Complete the README and VPS runbook.
3. Run a small transfer between two machines.
4. Verify the received file against the original SHA-256.
5. Measure actual network and disk usage.
6. Only then run larger tests, including the 10 GB test.






Profile	Traffic	What it tests
1. Text	Repeated text, JSON and CSV records	Compression of highly repetitive data
2. Mixed	Text, JSON, logs and binary blocks	Typical application traffic
3. Binary	Images, random bytes and other incompressible data	Framing and transmission when compression offers little benefit

Each test should record:
- Original payload size and SHA-256.
- Transmitted bytes and compression ratio.
- Sequence numbers and frame integrity.
- Server receive and decompression results.
- Restored payload size and SHA-256.
- Transfer time, throughput and errors.





Command 1 — VPS2
Receiver

cd ~/SW103K-Eric-Validation && sudo ./VPS2/run_receiver.sh


Expected: dependency check, license check, server startup, port 10300 readiness, and receiver log location.


Command 2 — VPS1
Validation

cd ~/SW103K-Eric-Validation && ./VPS1/03_run_client.sh VPS2_PUBLIC_IP





































repare the two VPS machines
Copy the complete SW103K-Eric-Validation directory to both VPS machines, preserving:
- bin/libsw103k_codec.so
- scripts/two_vps.py
- test-data/
- evidence/source-snapshot/
Both VPS machines must use compatible Linux architectures and Python 3. The receiver needs inbound TCP port 10300 permitted by its firewall.

. Eric's two commands
VPS2 — start receiver
cd SW103K-Eric-Validation
python3 scripts/two_vps.py receive --bind 0.0.0.0 --port 10300



VPS1 — send test data
cd SW103K-Eric-Validation
python3 scripts/two_vps.py send --host VPS2_PUBLIC_IP --port 10300



Replace VPS2_PUBLIC_IP with the actual public IP of VPS2.













Next: independent VPS1 → VPS2 test
- VPS2 (africloud): runs the receiver and stores the compressed archives.
- VPS (contabo)1: runs the sender and transmits the three datasets.
- VPS2 must confirm persistence before VPS1 sends the decompression trigger.
- VPS2 must then report all three SHA256 checks as PASS.
Do not describe the independent VPS test as passed until we have both machines' actual outputs.

ssh root@62.171.190.37
pwd  P3j786kOQOaJlc0aA
public IP address of VPS1 and VPS
root@41.220.3.33 VPS1 africloud
root@62.171.190.37 VPS2 contabo