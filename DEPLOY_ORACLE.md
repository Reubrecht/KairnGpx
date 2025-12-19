# Deploying Kairn to Oracle Cloud

This guide explains how to deploy Kairn on a fresh Oracle Cloud Instance (e.g., using Oracle Linux 8 or Ubuntu).

## 1. Prerequisites (Server Setup)

### Connect to your instance
```bash
ssh -i /path/to/your/key.key opc@your-instance-ip
```

### Install Docker & Docker Compose and Git
On Oracle Linux 8 / 9:
```bash
sudo dnf config-manager --add-repo=https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# You need to logout and login again for group changes to take effect
exit
```
*Reconnect to the server.*

Install Docker Compose Plugin:
```bash
sudo dnf install -y docker-compose-plugin
```

## 2. Firewall Configuration (Oracle Cloud + OS)
Ensure you have allowed port 80 and 443 in your Oracle Cloud **Security List** (Ingress Rules).

On the instance itself (Oracle Linux uses firewalld):
```bash
sudo firewall-cmd --permanent --zone=public --add-service=http
sudo firewall-cmd --permanent --zone=public --add-service=https
sudo firewall-cmd --reload
```

## 3. Clone Repository & Setup

Clone the code:
```bash
git clone https://github.com/Reubrecht/Kairn.git
cd Kairn
```

Create environment file:
```bash
cp .env.freebox.example .env
nano .env
```
**Important**: Update `.env` with your desired secrets (Passwords, API Keys, etc).

## 4. HTTPS Configuration (Caddy)
Edit the `Caddyfile` to use your domain name.
```bash
nano Caddyfile
```
Change `app.mykairn.fr` to your actual domain (pointed to the server IP via DNS).
Example:
```
your-domain.com {
    reverse_proxy kairn:8000
}
```

## 5. Deploy

Run the deployment script:
```bash
chmod +x scripts/deploy-oracle.sh
./scripts/deploy-oracle.sh
```

## Useful Commands

- **View logs**:
  ```bash
  docker compose -f docker-compose.oracle.yml logs -f
  ```
- **Stop everything**:
  ```bash
  docker compose -f docker-compose.oracle.yml down
  ```
- **Backup Database**:
  ```bash
  docker compose -f docker-compose.oracle.yml exec db pg_dump -U kairn kairn > backup.sql
  ```
