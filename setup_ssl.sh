#!/bin/bash
# SSL Certificate Setup Script
# Uses Let's Encrypt for free SSL certificates

set -e

DOMAIN="yourdomain.com"
EMAIL="admin@yourdomain.com"

echo "🔐 Setting up SSL certificates for $DOMAIN"

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update
        sudo apt-get install -y certbot python3-certbot-nginx
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew install certbot
    else
        echo "❌ Please install certbot manually"
        exit 1
    fi
fi

# Stop nginx if running
echo "Stopping nginx..."
sudo systemctl stop nginx 2>/dev/null || docker-compose stop nginx 2>/dev/null || true

# Get certificate
echo "Obtaining SSL certificate..."
sudo certbot certonly \
    --standalone \
    --preferred-challenges http \
    --agree-tos \
    --email "$EMAIL" \
    --no-eff-email \
    -d "$DOMAIN" \
    -d "www.$DOMAIN"

if [ $? -eq 0 ]; then
    echo "✅ SSL certificate obtained successfully!"
    echo ""
    echo "Certificate files location:"
    echo "  - Certificate: /etc/letsencrypt/live/$DOMAIN/fullchain.pem"
    echo "  - Private Key: /etc/letsencrypt/live/$DOMAIN/privkey.pem"
    echo ""
    echo "Next steps:"
    echo "1. Update nginx/nginx.conf with your domain name"
    echo "2. Start nginx: sudo systemctl start nginx"
    echo "3. Test auto-renewal: sudo certbot renew --dry-run"
else
    echo "❌ Failed to obtain SSL certificate"
    exit 1
fi

# Set up auto-renewal
echo "Setting up automatic renewal..."
sudo crontab -l 2>/dev/null | { cat; echo "0 0 1 * * certbot renew --quiet && systemctl reload nginx"; } | sudo crontab -

echo "✅ Auto-renewal configured (runs monthly)"
echo ""
echo "🎉 SSL setup complete!"
