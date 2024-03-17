/usr/bin/sudo pkill -F /home/pi/update.pid
/usr/bin/sudo pkill -F /home/pi/metarpid.pid
/usr/bin/sudo /usr/bin/python3 /home/pi/update.py & echo $! > /home/pi/update.pid
