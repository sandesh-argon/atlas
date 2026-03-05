# Quick Launch Guide - A4 Phase 3

**Updated**: November 17, 2025
**Status**: ✅ READY TO LAUNCH

---

## Decision Matrix (CORRECTED)

| Metric | Local (10 cores) | AWS SPOT (192 cores) |
|--------|------------------|----------------------|
| **Runtime** | 6 days | **10-12 hours** |
| **Cost** | $0 | **$32** |
| **Speed** | 14.7 edges/min | **235 edges/min (16× faster)** |
| **Value** | Free | **$5.57/day of saved time** |

**Decision**: AWS if your time is worth >$5.57/day (spoiler: it is for PhD research)

---

## OPTION 1: Local Launch (FREE, 6 DAYS)

### Step 1: Clean Environment (2 min)
```bash
cd <repo-root>/v2.0/phaseA/A4_effect_quantification

# Kill ALL old processes
pkill -9 -f "step3_effect_estimation"
pkill -9 -f "step2_backdoor"
pkill -9 -f "loky.backend"

# Verify clean (should show 0-2)
ps aux | grep python | grep -E "(step|loky)" | grep -v grep | wc -l
```

### Step 2: Launch Full Run
```bash
# Run with clean logs
python scripts/step3_effect_estimation_lasso.py \
  --n_jobs 10 \
  --bootstrap 100 \
  --effect_threshold 0.12 \
  --checkpoint_every 5000 \
  > logs/step3_full_run_local.log 2>&1 &

# Note the PID
echo $! > logs/step3_pid.txt
```

### Step 3: Monitor Progress (every 4 hours)
```bash
# Check progress
tail -50 logs/step3_full_run_local.log | grep "INFO"

# Check thermals
sensors | grep Tctl

# Check workers
ps aux | grep LokyProcess | grep -v grep | wc -l  # Should be 10
```

### Step 4: Estimated Timeline
- **Start**: Day 1, morning
- **First checkpoint (5K)**: +6 hours
- **Halfway (65K)**: +4.5 days
- **Complete**: **+6 days**

---

## OPTION 2: AWS Launch ($32, 11 HOURS) - RECOMMENDED

### Prerequisites (10 min)
- [ ] AWS account with S3 access
- [ ] EC2 key pair created
- [ ] Security group allowing SSH (port 22)
- [ ] S3 bucket created

### Step 1: Package and Upload (5 min)
```bash
cd <repo-root>/v2.0/phaseA/A4_effect_quantification

# Package code and data
tar -czf A4_package.tar.gz \
  scripts/ \
  outputs/parent_adjustment_sets.pkl \
  ../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl

# Create requirements file
cat > requirements.txt <<EOF
numpy>=1.24.0
pandas>=2.0.0
scikit-learn>=1.3.0
joblib>=1.3.0
psutil>=5.9.0
requests>=2.31.0
EOF

# Upload to S3 (replace YOUR-BUCKET)
aws s3 cp A4_package.tar.gz s3://YOUR-BUCKET/A4/
aws s3 cp requirements.txt s3://YOUR-BUCKET/A4/
```

### Step 2: Launch SPOT Instance (3 min)
```bash
# Request SPOT instance
aws ec2 request-spot-instances \
  --spot-price "4.83" \
  --instance-count 1 \
  --type "one-time" \
  --launch-specification file://spot-spec.json

# spot-spec.json:
{
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
}

# Wait for instance (get IP address)
# ... or use AWS Console to get instance IP ...
```

### Step 3: SSH and Setup (15 min)
```bash
# SSH into instance
ssh -i ~/.ssh/YOUR-KEY.pem ec2-user@INSTANCE-IP

# Install Python 3.11+
sudo yum install -y python3.11 python3.11-pip tmux

# Download package
aws s3 cp s3://YOUR-BUCKET/A4/A4_package.tar.gz .
aws s3 cp s3://YOUR-BUCKET/A4/requirements.txt .

# Extract
tar -xzf A4_package.tar.gz

# Install dependencies
pip3.11 install -r requirements.txt

# Create directories
mkdir -p logs checkpoints outputs
```

### Step 4: Validation Test (5 min)
```bash
# Test with 100 edges to verify setup
python3.11 scripts/step3_effect_estimation_lasso.py \
  --sample_size 100 \
  --n_jobs 192 \
  --bootstrap 100

# Verify:
# - All 192 cores active (htop)
# - Processing rate >200 edges/min
# - No errors in output
```

### Step 5: Launch Full Run in tmux
```bash
# Start tmux session (survives disconnect)
tmux new -s A4

# Launch full run
python3.11 scripts/step3_effect_estimation_lasso.py \
  --n_jobs 192 \
  --bootstrap 100 \
  --effect_threshold 0.12 \
  --checkpoint_every 5000 \
  | tee logs/step3_full_run_aws.log

# Detach from tmux: Ctrl+B, then D
# Reattach later: tmux attach -t A4
```

### Step 6: Monitor (every 2 hours)
```bash
# SSH back in
ssh -i ~/.ssh/YOUR-KEY.pem ec2-user@INSTANCE-IP

# Reattach to tmux
tmux attach -t A4

# Check progress
tail -50 logs/step3_full_run_aws.log | grep "INFO"

# Expected:
# ✅ Chunk complete: 50000/129989 (38.5%)
# Rate: 3.92 edges/sec | ETA: 5.6 hours
```

### Step 7: Download Results & Terminate (10 min)
```bash
# Once complete, compress results
tar -czf A4_results.tar.gz \
  outputs/lasso_effect_estimates.pkl \
  checkpoints/ \
  logs/step3_full_run_aws.log

# Upload to S3
aws s3 cp A4_results.tar.gz s3://YOUR-BUCKET/A4/results/

# Download locally
aws s3 cp s3://YOUR-BUCKET/A4/results/A4_results.tar.gz .

# CRITICAL: Terminate instance
aws ec2 terminate-instances --instance-ids i-XXXXX
```

### Step 8: Verify Results
```bash
# Extract
tar -xzf A4_results.tar.gz

# Verify
python -c "
import pickle
import pandas as pd

results = pd.read_pickle('outputs/lasso_effect_estimates.pkl')
print(f'Total edges: {len(results):,}')
validated = results[results['status'] == 'success']
print(f'Validated: {len(validated):,} ({100*len(validated)/len(results):.1f}%)')
print(f'Mean effect size: {validated[\"beta\"].abs().mean():.3f}')
print(f'Mean controls: {validated[\"n_selected\"].mean():.1f}')
"
```

**Expected Output**:
- Total edges: 129,989
- Validated: ~93,000 (72%)
- Mean effect size: 0.30-0.40
- Mean controls: 6-15

---

## Timeline Comparison

### Local
```
Day 1: 00:00 - Launch
Day 1: 06:00 - First checkpoint (5K edges)
Day 3: 12:00 - Halfway (65K edges)
Day 6: 00:00 - COMPLETE ✅
```

### AWS
```
Hour 0: 00:00 - Launch
Hour 0: 21 - First checkpoint (5K edges)
Hour 4: 38 - Halfway (65K edges)
Hour 11: 00 - COMPLETE ✅
```

**Time Saved**: 5 days, 13 hours

---

## Recovery from Interruption

### If Process Dies (Local or AWS)

```bash
# 1. Find latest checkpoint
latest=$(ls -t checkpoints/effect_estimation_checkpoint_*.pkl | head -1)
echo "Latest checkpoint: $latest"

# 2. Clean processes (local only)
pkill -9 -f step3_effect_estimation
pkill -9 -f loky.backend

# 3. Resume from checkpoint
python scripts/step3_effect_estimation_lasso.py \
  --n_jobs 10 \  # or 192 for AWS
  --bootstrap 100 \
  --resume $latest \
  | tee -a logs/step3_full_run_resumed.log
```

**Max Loss**: 21 minutes of work (5K edges)

---

## Cost Summary (AWS)

| Item | Cost |
|------|------|
| c7i.48xlarge SPOT (11 hrs @ $2.90/hr) | $31.90 |
| EBS storage (100 GB, 1 day) | $0.27 |
| Data transfer (S3) | $0.09 |
| **TOTAL** | **$32.26** |

**vs On-Demand**: $105 (save $73 with SPOT)
**vs Local**: Save 5.75 days for $32

---

## Quick Decision Tool

**Are you willing to pay $5.57/day to save time?**
- **YES** → AWS SPOT ($32, 11 hours)
- **NO** → Local (Free, 6 days)

**Is your deadline <6 days away?**
- **YES** → AWS SPOT (only option)
- **NO** → Either works

**Do you need your local machine free?**
- **YES** → AWS SPOT
- **NO** → Local is fine

**PhD researcher with typical budget?**
- **ALWAYS** → AWS SPOT (time >> money in PhD)

---

## Troubleshooting

### Local: High temps (>90°C)
```bash
# Reduce cores to 8
pkill -9 -f step3_effect_estimation
pkill -9 -f loky.backend

python scripts/step3_effect_estimation_lasso.py \
  --n_jobs 8 \  # Reduced from 10
  --resume <latest_checkpoint>
```

### AWS: SPOT interrupted
```bash
# Launch new instance, download checkpoints, resume
# See full AWS_DEPLOYMENT_PLAN.md for details
```

### Any: Want to check if running
```bash
# Check process
ps aux | grep step3_effect_estimation | grep -v grep

# Check latest log entry
tail -1 logs/step3_full_run_*.log
```

---

## Files Reference

- **Full details**: `AWS_DEPLOYMENT_PLAN.md` (21 pages)
- **Test results**: `A4_PHASE3_TEST_RESULTS.md`
- **Implementation**: `A4_DEPLOYMENT_READY.md`
- **This file**: Quick commands only

---

**Ready to launch? Pick your option and follow the steps above!** 🚀
