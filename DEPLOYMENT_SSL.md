# Production Deployment Guide - HTTPS/SSL

## 🔒 SSL Certificate Setup

### Option 1: Let's Encrypt (Free, Recommended)

1. **Run the setup script:**
```bash
# Edit the domain in setup_ssl.sh first
sudo ./setup_ssl.sh
```

2. **Update nginx.conf:**
```bash
# Replace 'yourdomain.com' with your actual domain
sed -i 's/yourdomain.com/your-actual-domain.com/g' nginx/nginx.conf
```

3. **Deploy with nginx:**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Option 2: Manual Setup

1. **Get certificates:**
```bash
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
```

2. **Update nginx configuration:**
Edit `nginx/nginx.conf` and replace domain names.

3. **Start services:**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 🔐 Security Checklist

Before going live:

- [ ] SSL certificates installed and working
- [ ] HTTPS redirect enabled (HTTP → HTTPS)
- [ ] Security headers configured
- [ ] CORS set to production domain only
- [ ] JWT_SECRET_KEY changed to strong random value
- [ ] All passwords changed from defaults
- [ ] Sentry configured for error tracking
- [ ] Database backups automated

## 🧪 Testing SSL

```bash
# Test SSL configuration
curl -I https://yourdomain.com

# Check SSL grade (external tool)
# Visit: https://www.ssllabs.com/ssltest/
```

## 🔄 Auto-Renewal

Let's Encrypt certificates expire after 90 days. Auto-renewal is configured via cron:

```bash
# Check if auto-renewal works
sudo certbot renew --dry-run
```

## 🚨 Troubleshooting

**Issue: "Connection refused"**
- Check if port 80 and 443 are open in firewall
- Verify nginx is running: `docker ps | grep nginx`

**Issue: "Certificate error"**
- Check certificate files exist: `ls /etc/letsencrypt/live/yourdomain.com/`
- Verify nginx.conf has correct paths

**Issue: "Too many redirects"**
- Check HTTPS redirect is not conflicting with proxy settings
- Verify X-Forwarded-Proto header is set
