# AWS Deployment Guide - CarDealersPro

This guide provides step-by-step instructions for deploying CarDealersPro to AWS using Elastic Beanstalk or ECS.

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed and configured
- Docker installed locally
- GitHub repository with the project code

## Option 1: AWS Elastic Beanstalk (Recommended for Beginners)

### Step 1: Prepare Your Application

1. **Push your code to GitHub**
   ```bash
   git add .
   git commit -m "Ready for AWS deployment"
   git push origin main
   ```

2. **Ensure your `.gitignore` excludes sensitive files**
   - `.env`
   - `*.pem`
   - `venv/`
   - `__pycache__/`

### Step 2: Create AWS Elastic Beanstalk Application

1. **Install AWS CLI** (if not already installed)
   ```bash
   # Windows
   winget install Amazon.AWSCLI

   # Verify installation
   aws --version
   ```

2. **Configure AWS CLI**
   ```bash
   aws configure
   # Enter your AWS Access Key ID
   # Enter your AWS Secret Access Key
   # Enter default region (e.g., us-east-1)
   # Enter default output format (json)
   ```

3. **Install EB CLI**
   ```bash
   pip install awsebcli
   ```

4. **Initialize Elastic Beanstalk**
   ```bash
   cd CarDealersPro
   eb init
   # Select a region (e.g., us-east-1)
   # Enter an application name (e.g., CarDealersPro)
   # Select a platform (Docker)
   # Select "No" for SSH setup (unless needed)
   ```

### Step 3: Create Environment

1. **Create the environment**
   ```bash
   eb create production
   # This will create a new environment with default settings
   ```

2. **Wait for the environment to be ready**
   - This may take 5-10 minutes
   - Check status with: `eb status`

### Step 4: Configure Environment Variables

1. **Set environment variables via AWS Console**
   - Go to Elastic Beanstalk → Configuration → Software
   - Add the following environment variables:

   ```env
   DATABASE_URL=postgresql://username:password@hostname:5432/database_name
   ALGORITHM=RS256
   ACCESS_TOKEN_EXPIRE_MINUTES=60
   PRIVATE_KEY_BASE64=<your_base64_encoded_private_key>
   PUBLIC_KEY_BASE64=<your_base64_encoded_public_key>
   ```

2. **Or set via EB CLI**
   ```bash
   eb setenv DATABASE_URL="postgresql://..."
   eb setenv ALGORITHM="RS256"
   eb setenv ACCESS_TOKEN_EXPIRE_MINUTES="60"
   eb setenv PRIVATE_KEY_BASE64="..."
   eb setenv PUBLIC_KEY_BASE64="..."
   ```

### Step 5: Set Up AWS RDS PostgreSQL

1. **Create RDS Instance**
   - Go to AWS Console → RDS → Create database
   - Select PostgreSQL
   - Choose Free Tier (if eligible)
   - Set master username and password
   - Create database name: `CarDealersPro`

2. **Get Database Connection String**
   - Go to RDS → Instances → Select your instance
   - Copy the endpoint (hostname)
   - Connection string format:
     ```
     postgresql://master_username:password@endpoint:5432/CarDealersPro
     ```

3. **Update DATABASE_URL in Elastic Beanstalk**
   ```bash
   eb setenv DATABASE_URL="postgresql://master_username:password@endpoint:5432/CarDealersPro"
   ```

### Step 6: Run Database Migrations

1. **SSH into the Elastic Beanstalk instance**
   ```bash
   eb ssh
   ```

2. **Navigate to application directory**
   ```bash
   cd /var/app/current
   ```

3. **Run migrations**
   ```bash
   python -m alembic upgrade head
   ```

4. **Exit SSH**
   ```bash
   exit
   ```

### Step 7: Deploy Your Application

1. **Deploy the application**
   ```bash
   eb deploy
   ```

2. **Monitor deployment**
   ```bash
   eb events
   ```

3. **Check application status**
   ```bash
   eb status
   ```

### Step 8: Test Your Application

1. **Get the application URL**
   ```bash
   eb printenv | grep CNAME
   ```

2. **Test health endpoint**
   ```bash
   curl http://your-app-url.elasticbeanstalk.com/health
   # Expected response: {"status": "ok"}
   ```

3. **Test root endpoint**
   ```bash
   curl http://your-app-url.elasticbeanstalk.com/
   ```

---

## Option 2: AWS ECS (Advanced)

### Step 1: Create ECR Repository

1. **Create repository**
   ```bash
   aws ecr create-repository --repository-name cardealerspro
   ```

2. **Login to ECR**
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
   ```

### Step 2: Build and Push Docker Image

1. **Build the image**
   ```bash
   docker build -t cardealerspro .
   ```

2. **Tag the image**
   ```bash
   docker tag cardealerspro:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/cardealerspro:latest
   ```

3. **Push the image**
   ```bash
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/cardealerspro:latest
   ```

### Step 3: Create ECS Task Definition

1. **Create task definition file** (`task-definition.json`)
   ```json
   {
     "family": "cardealerspro",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "256",
     "memory": "512",
     "containerDefinitions": [
       {
         "name": "cardealerspro",
         "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/cardealerspro:latest",
         "essential": true,
         "portMappings": [
           {
             "containerPort": 8000,
             "protocol": "tcp"
           }
         ],
         "environment": [
           {
             "name": "PORT",
             "value": "8000"
           }
         ],
         "secrets": [
           {
             "name": "DATABASE_URL",
             "valueFrom": "arn:aws:secretsmanager:region:account-id:secret:cardealerspro-db-url"
           },
           {
             "name": "PRIVATE_KEY_BASE64",
             "valueFrom": "arn:aws:secretsmanager:region:account-id:secret:cardealerspro-private-key"
           },
           {
             "name": "PUBLIC_KEY_BASE64",
             "valueFrom": "arn:aws:secretsmanager:region:account-id:secret:cardealerspro-public-key"
           }
         ],
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/cardealerspro",
             "awslogs-region": "us-east-1",
             "awslogs-stream-prefix": "ecs"
           }
         }
       }
     ]
   }
   ```

2. **Register task definition**
   ```bash
   aws ecs register-task-definition --cli-input-json file://task-definition.json
   ```

### Step 4: Create ECS Cluster

1. **Create cluster**
   ```bash
   aws ecs create-cluster --cluster-name cardealerspro-cluster
   ```

### Step 5: Create ECS Service

1. **Create service**
   ```bash
   aws ecs create-service \
     --cluster cardealerspro-cluster \
     --service-name cardealerspro-service \
     --task-definition cardealerspro \
     --desired-count 1 \
     --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[subnet-12345678],securityGroups=[sg-12345678],assignPublicIp=ENABLED}"
   ```

### Step 6: Create Application Load Balancer

1. **Create target group**
   ```bash
   aws elbv2 create-target-group \
     --name cardealerspro-tg \
     --port 8000 \
     --protocol HTTP \
     --target-type ip \
     --vpc-id vpc-12345678
   ```

2. **Create load balancer**
   ```bash
   aws elbv2 create-load-balancer \
     --name cardealerspro-lb \
     --subnets subnet-12345678 subnet-87654321 \
     --security-groups sg-12345678
   ```

3. **Create listener**
   ```bash
   aws elbv2 create-listener \
     --load-balancer-arn <load-balancer-arn> \
     --protocol HTTP \
     --port 80 \
     --default-actions Type=forward,TargetGroupArn=<target-group-arn>
   ```

---

## Security Best Practices

### 1. Use AWS Secrets Manager

**Store sensitive data in Secrets Manager:**
```bash
aws secretsmanager create-secret \
  --name cardealerspro-db-url \
  --secret-string "postgresql://username:password@hostname:5432/database"

aws secretsmanager create-secret \
  --name cardealerspro-private-key \
  --secret-string "<base64_encoded_private_key>"

aws secretsmanager create-secret \
  --name cardealerspro-public-key \
  --secret-string "<base64_encoded_public_key>"
```

### 2. Enable HTTPS

1. **Get SSL certificate from AWS Certificate Manager**
2. **Configure load balancer to use HTTPS**
3. **Redirect HTTP to HTTPS**

### 3. Use VPC and Security Groups

- Restrict database access to only your ECS/Elastic Beanstalk instances
- Use security groups to control inbound/outbound traffic

### 4. Enable CloudWatch Logs

- Application logs are automatically sent to CloudWatch
- Set up log retention policies
- Create metric filters for errors

---

## Monitoring and Logging

### CloudWatch Metrics

Elastic Beanstalk and ECS automatically send metrics to CloudWatch:
- CPU utilization
- Memory utilization
- Request count
- Response time
- Error rate

### CloudWatch Logs

Application logs are available in CloudWatch Logs:
- Elastic Beanstalk: `/aws/elasticbeanstalk/<environment-name>/var/log/web.stdout.log`
- ECS: `/ecs/cardealerspro`

### Set Up Alarms

1. **Go to CloudWatch → Alarms**
2. **Create alarm for high CPU usage**
3. **Create alarm for high error rate**
4. **Set up SNS notifications**

---

## Troubleshooting

### Application Not Starting

1. **Check logs**
   ```bash
   eb logs --all  # Elastic Beanstalk
   aws logs tail /ecs/cardealerspro --follow  # ECS
   ```

2. **Check environment variables**
   ```bash
   eb printenv  # Elastic Beanstalk
   ```

3. **Check database connectivity**
   - Verify DATABASE_URL is correct
   - Check security group allows database access

### Database Connection Errors

1. **Verify RDS instance is running**
2. **Check security group allows access from your application**
3. **Verify DATABASE_URL format**
4. **Check if migrations were run**

### Health Check Failing

1. **Verify health endpoint is accessible**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check if port is correct**
   - Default: 8000
   - Hugging Face: 7860
   - Custom: Set PORT environment variable

---

## Cost Optimization

### Free Tier Benefits

- **Elastic Beanstalk**: 750 hours/month for t2.micro or t3.micro instances
- **RDS**: 750 hours/month for db.t2.micro or db.t3.micro instances
- **ECS Fargate**: 400 GB-month of storage

### Cost Saving Tips

1. **Use t3.micro or t2.micro instances for development**
2. **Set up auto-scaling to scale down during low traffic**
3. **Use reserved instances for production**
4. **Enable CloudWatch Logs retention to reduce storage costs**

---

## Scaling

### Auto Scaling (Elastic Beanstalk)

1. **Go to Configuration → Capacity**
2. **Enable auto scaling**
3. **Set minimum/maximum instances**
4. **Configure scaling policies based on CPU or memory**

### Auto Scaling (ECS)

1. **Create target tracking scaling policy**
2. **Set target CPU utilization (e.g., 70%)**
3. **Set minimum/maximum task count**

---

## Backup and Recovery

### RDS Backups

- **Automated backups**: Enabled by default (7-day retention)
- **Manual snapshots**: Create before major changes
- **Point-in-time recovery**: Restore to any time within backup window

### Application Backups

- **Code**: Stored in GitHub
- **Environment variables**: Store in AWS Systems Manager Parameter Store
- **Docker images**: Stored in ECR

---

## CI/CD Pipeline

### AWS CodePipeline

1. **Create pipeline**
   - Source: GitHub
   - Build: CodeBuild
   - Deploy: Elastic Beanstalk or ECS

2. **CodeBuild buildspec.yml**
   ```yaml
   version: 0.2
   phases:
     install:
       runtime-versions:
         python: 3.11
     pre_build:
       commands:
         - pip install -r requirements.txt
     build:
       commands:
         - docker build -t cardealerspro .
         - docker tag cardealerspro:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/cardealerspro:latest
     post_build:
       commands:
         - aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
         - docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/cardealerspro:latest
   ```

---

## Summary

**Elastic Beanstalk** is recommended for:
- Beginners
- Quick deployment
- Managed infrastructure
- Lower operational overhead

**ECS** is recommended for:
- Advanced users
- More control over infrastructure
- Microservices architecture
- Complex scaling requirements

**Next Steps:**
1. Choose deployment option (Elastic Beanstalk or ECS)
2. Follow the step-by-step guide
3. Test thoroughly
4. Set up monitoring and alerts
5. Configure auto-scaling for production
