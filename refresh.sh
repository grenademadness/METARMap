/usr/bin/sudo pkill -F /home/pi/offpid.pid
/usr/bin/sudo pkill -F /home/pi/metarpid.pid
echo Checking AWS Bucket Updates
/usr/bin/sudo /usr/bin/python3 /home/pi/update.py
/usr/bin/sudo /usr/bin/python3 /home/pi/metar.py & echo $! > /home/pi/metarpid.pid
echo Restarting
