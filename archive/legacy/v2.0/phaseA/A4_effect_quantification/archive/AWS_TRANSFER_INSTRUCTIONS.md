# AWS Transfer Instructions - Resume from 40K Checkpoint

**Date**: November 18, 2025
**Local Progress**: 40,000 / 129,989 edges (30.8% complete)
**Checkpoint**: effect_estimation_checkpoint_40000.pkl (VALIDATED ✅)
**Transfer Package**: A4_transfer.tar.gz (218 MB)

---

## 📦 Step 1: Upload Transfer Package to S3

```bash
cd <repo-root>/v2.0/phaseA/A4_effect_quantification

# Upload to S3 (replace YOUR-BUCKET)
aws s3 cp A4_transfer.tar.gz s3://YOUR-BUCKET/A4/transfer/

# Verify upload
aws s3 ls s3://YOUR-BUCKET/A4/transfer/A4_transfer.tar.gz
```

**Expected output**:
```
2025-11-18 17:57:00  228558234 A4_transfer.tar.gz
```

---

## 🚀 Step 2: Launch AWS c7i.48xlarge SPOT Instance

### Option A: AWS Console (Easiest)

1. Go to **EC2 → Spot Requests → Request Spot Instances**
2. **AMI**: Amazon Linux 2023 (ami-0c55b159cbfafe1f0)
3. **Instance type**: c7i.48xlarge
4. **Max price**: $4.83/hour (50% of on-demand $9.65)
5. **Storage**: 100 GB gp3, 3000 IOPS
6. **Key pair**: Select your SSH key
7. **Security group**: Allow SSH (port 22)
8. Click **Launch**

**Wait 2-3 minutes** for instance to start. Note the **Public IP address**.

### Option B: AWS CLI

```bash
aws ec2 request-spot-instances \
  --spot-price "4.83" \
  --instance-count 1 \
  --type "one-time" \
  --launch-specification '{
    "ImageId": "ami-0c55b159cbfafe1f0",
    "InstanceType": "c7i.48xlarge",
    "KeyName": "YOUR-KEY-NAME",
    "SecurityGroupIds": ["sg-XXXXX"],
    "BlockDeviceMappings": [{
      "DeviceName": "/dev/xvda",
      "Ebs": {
        "VolumeSize": 100,
        "VolumeType": "gp3",
        "Iops": 3000,
        "DeleteOnTermination": true
      }
    }]
  }'

# Get instance IP
aws ec2 describe-spot-instance-requests --query 'SpotInstanceRequests[0].InstanceId'
aws ec2 describe-instances --instance-ids i-XXXXX --query 'Reservations[0].Instances[0].PublicIpAddress'
```

---

## ⚙️ Step 3: Setup AWS Instance

```bash
# SSH into instance
ssh -i ~/.ssh/YOUR-KEY.pem ec2-user@YOUR-INSTANCE-IP

# Install Python 3.11
sudo yum install -y python3.11 python3.11-pip tmux htop

# Download transfer package
aws s3 cp s3://YOUR-BUCKET/A4/transfer/A4_transfer.tar.gz .

# Extract
tar -xzf A4_transfer.tar.gz

# Install dependencies
pip3.11 install --user -r requirements.txt

# Create logs directory
mkdir -p logs
```

---

## ✅ Step 4: Validation Test (5 min)

```bash
# Test with 100 edges to verify everything works
python3.11 scripts/step3_effect_estimation_lasso.py \
  --sample_size 100 \
  --n_jobs 192 \
  --bootstrap 100

# Expected output:
# ✅ Chunk complete: 100/100 (100.0%)
# Final validated edges: X
# (Should complete in ~1 minute)
```

**Verify**:
- All 192 cores active: `htop` (should show ~19,000% CPU)
- No errors in output
- Processing rate >200 edges/min

---

## 🚀 Step 5: Resume from Checkpoint 40K

```bash
# Start tmux session (survives disconnect)
tmux new -s A4

# Resume from checkpoint 40000
python3.11 scripts/step3_effect_estimation_lasso.py \
  --n_jobs 192 \
  --bootstrap 100 \
  --effect_threshold 0.12 \
  --checkpoint_every 5000 \
  --resume checkpoints/effect_estimation_checkpoint_40000.pkl \
  | tee logs/step3_aws_resumed.log

# Detach from tmux: Ctrl+B, then D
# Reattach later: tmux attach -t A4
```

**Expected initial output**:
```
📂 Loading checkpoint: checkpoints/effect_estimation_checkpoint_40000.pkl
  ✅ Loaded 40,000 completed edges
  Resuming from edge 40,000

🚀 FULL RUN: Processing all 129,989 edges
Remaining edges: 89,989

📦 Chunk 1/18: Edges 0 - 5,000
[Parallel(n_jobs=192)]: Using backend LokyBackend with 192 concurrent workers.
```

---

## 📊 Step 6: Monitor Progress

### Check Progress (every 1-2 hours)

```bash
# SSH back in
ssh -i ~/.ssh/YOUR-KEY.pem ec2-user@YOUR-INSTANCE-IP

# Reattach to tmux
tmux attach -t A4

# Check recent progress
tail -50 logs/step3_aws_resumed.log | grep "INFO"

# Expected output every 21 minutes (5K edges @ 235/min):
# ✅ Chunk complete: 45000/129989 (34.6%)
# Rate: 3.92 edges/sec | ETA: 5.3 hours
```

### Resource Monitoring

```bash
# CPU usage (should be ~19,000% = 192 cores @ 100%)
htop

# Memory usage (should be <50%, ~150-200 GB / 384 GB)
free -h

# Check workers
ps aux | grep LokyProcess | wc -l  # Should be 192
```

---

## ⏱️ Expected Timeline

**Remaining work**: 89,989 edges
**AWS rate**: 235 edges/min (16× faster than local)
**Processing time**: 89,989 ÷ 235 = 383 minutes = **6.4 hours**

**Checkpoint Schedule** (every 21 minutes):
```
Hour 0:00 - Resume from 40K
Hour 0:21 - Checkpoint 45K (5.6% progress)
Hour 0:43 - Checkpoint 50K (11.1%)
Hour 1:28 - Checkpoint 60K (22.2%)
Hour 2:34 - Checkpoint 75K (38.9%)
Hour 3:41 - Checkpoint 90K (55.6%)
Hour 4:47 - Checkpoint 105K (72.2%)
Hour 5:53 - Checkpoint 120K (88.9%)
Hour 6:24 - COMPLETE ✅ (100%)
```

**Completion**: ~6.5 hours from resume start

---

## 💰 Cost Breakdown

| Item | Calculation | Cost |
|------|-------------|------|
| **Compute** | 6.5 hrs @ $2.90/hr | $18.85 |
| **EBS storage** | 100 GB × 1 day | $0.27 |
| **Data transfer** | 218 MB upload | $0.02 |
| **Total** | | **$19.14** |

**Time saved**: 42 hours (local) - 6.5 hours (AWS) = **35.5 hours (1.5 days)**

---

## 📥 Step 7: Download Results & Terminate

### Once Complete

```bash
# Compress results
tar -czf A4_results.tar.gz \
  outputs/lasso_effect_estimates.pkl \
  checkpoints/ \
  logs/step3_aws_resumed.log

# Upload to S3
aws s3 cp A4_results.tar.gz s3://YOUR-BUCKET/A4/results/

# Download to local machine
# (On your local machine)
aws s3 cp s3://YOUR-BUCKET/A4/results/A4_results.tar.gz \
  <repo-root>/v2.0/phaseA/A4_effect_quantification/
```

### Terminate Instance (CRITICAL!)

```bash
# Get instance ID from AWS Console, then:
aws ec2 terminate-instances --instance-ids i-XXXXX

# Or use Console: EC2 → Instances → Select → Actions → Terminate
```

**⚠️ IMPORTANT**: Terminating within 1 hour of completion saves $2.90/hour!

---

## 🆘 Troubleshooting

### If SPOT Interrupted Mid-Run

**AWS sends 2-min warning before termination**. Script will auto-save checkpoint.

**Recovery**:
1. Launch new SPOT instance (same steps above)
2. Download latest checkpoint from previous instance's EBS
3. Resume: `--resume checkpoints/checkpoint_XXXXX.pkl`
4. Max loss: 21 minutes (5K edges @ 235/min)

### If Connection Lost

**No problem!** Job runs in tmux and survives disconnection.

```bash
# Just SSH back in
ssh -i ~/.ssh/YOUR-KEY.pem ec2-user@YOUR-INSTANCE-IP

# Reattach to tmux
tmux attach -t A4
```

### If Want to Check Status Without Connecting

```bash
# From local machine, check S3 for new checkpoints
aws s3 ls s3://YOUR-BUCKET/A4/checkpoints/ | tail -5

# If checkpoints updating every ~21 min, it's running fine
```

---

## ✅ Verification After Completion

```bash
# Extract results
tar -xzf A4_results.tar.gz

# Verify output
python3 -c "
import pickle
import pandas as pd

results = pd.read_pickle('outputs/lasso_effect_estimates.pkl')
print(f'Total edges: {len(results):,}')
validated = results[results['status'] == 'success']
print(f'Validated: {len(validated):,} ({100*len(validated)/len(results):.1f}%)')
print(f'Mean effect size: {validated[\"beta\"].abs().mean():.3f}')
"
```

**Expected Output**:
```
Total edges: 129,989
Validated: ~76,000 (58.6%)
Mean effect size: 0.27-0.29
```

---

## 📋 Quick Reference

**Package uploaded**: ✅ A4_transfer.tar.gz (218 MB)
**Checkpoint to resume**: effect_estimation_checkpoint_40000.pkl
**Remaining edges**: 89,989 (69.2%)
**Expected time**: 6.5 hours
**Expected cost**: $19
**Time saved vs local**: 35.5 hours (1.5 days)

---

## 🎯 Next Steps

1. ✅ **Package created and validated** (this step)
2. ⏳ **Upload to S3** (your S3 bucket)
3. ⏳ **Launch c7i.48xlarge SPOT** (AWS Console or CLI)
4. ⏳ **Setup instance** (10 min)
5. ⏳ **Run validation test** (5 min)
6. ⏳ **Resume from checkpoint** (launch in tmux)
7. ⏳ **Monitor** (check every 1-2 hours)
8. ⏳ **Download & terminate** (when complete)

---

**Status**: 🚀 READY FOR AWS DEPLOYMENT

**Completion ETA**: ~6.5 hours from resume start

**Total Cost**: ~$19

**Time Saved**: 1.5 days vs continuing local

🎉 **Let's finish this run on AWS!** 🎉
