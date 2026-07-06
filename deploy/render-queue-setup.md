# Render Queue Setup

Install Redis and Python dependencies:

```bash
sudo apt update
sudo apt install -y redis-server
cd /var/www/theupmedia
source env/bin/activate
pip install -r requirements.txt
```

Add these lines to `/var/www/theupmedia/.env`:

```env
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
LIVE_TV_RENDER_USE_CELERY=True
LIVE_TV_RENDER_ENCODER=cpu
```

For an NVIDIA GPU server with NVENC support:

```env
LIVE_TV_RENDER_ENCODER=nvenc
LIVE_TV_RENDER_NVENC_PRESET=p1
LIVE_TV_RENDER_NVENC_CQ=28
```

Install the worker service:

```bash
sudo cp /var/www/theupmedia/deploy/theupmedia-celery.service /etc/systemd/system/theupmedia-celery.service
sudo systemctl daemon-reload
sudo systemctl enable redis-server
sudo systemctl enable theupmedia-celery
sudo systemctl restart redis-server
sudo systemctl restart gunicorn
sudo systemctl restart theupmedia-celery
sudo systemctl restart apache2
```

Check status/logs:

```bash
sudo systemctl status theupmedia-celery
sudo journalctl -u theupmedia-celery -f
```

For Apache2, make sure media files are served directly:

```apache
Alias /media/ /var/www/theupmedia/media/
<Directory /var/www/theupmedia/media/>
    Require all granted
</Directory>

Alias /static/ /var/www/theupmedia/staticfiles/
<Directory /var/www/theupmedia/staticfiles/>
    Require all granted
</Directory>
```

Reload Apache after vhost changes:

```bash
sudo apache2ctl configtest
sudo systemctl reload apache2
```
