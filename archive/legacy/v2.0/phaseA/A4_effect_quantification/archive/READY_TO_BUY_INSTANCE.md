# ✅ READY TO BUY AWS INSTANCE

**Date**: November 17, 2025
**Status**: ALL CRITICAL FIXES APPLIED

---

## 🎯 Critical Fixes Applied (All 3 Done)

### ✅ Fix 1: Cost Estimates CORRECTED
- **Was**: $19 (8 hours @ $2.40/hr)
- **Now**: **$32** (11 hours @ $2.90/hr)
- **Reason**: Accounting for Amdahl's Law (16× speedup, not 19.2×)

### ✅ Fix 2: Runtime Projections CORRECTED
- **Was**: 7.7-8.8 hours
- **Now**: **10-12 hours**
- **Processing rate**: 230-240 edges/min (not 282)
- **Realistic scaling**: 83-85% efficiency (not 96%)

### ✅ Fix 3: Checkpoint Loss CORRECTED
- **Was**: 20 minutes
- **Now**: **21 minutes** (5,000 edges @ 235 edges/min)
- **Cost of interruption**: $1.02

### ✅ BONUS Fix: Warnings Suppression
- **Problem**: Warnings still appearing from worker processes
- **Solution**: Moved `warnings.filterwarnings()` inside `estimate_effect_lasso()` function
- **Result**: Clean logs confirmed

---

## 📊 Updated Decision Matrix

| Metric | Local (10 cores) | AWS SPOT (192 cores) |
|--------|------------------|----------------------|
| **Runtime** | 6 days (147 hours) | **11 hours** |
| **Cost** | $0 | **$32** |
| **Processing Rate** | 14.7 edges/min | **235 edges/min** |
| **Speedup** | 1× | **16×** |
| **Time Saved** | - | **5.75 days (138 hours)** |
| **Cost per Day Saved** | - | **$5.57/day** |
| **Results By** | 6 days from launch | **End of day** |

**Break-even**: AWS worth it if your time > $5.57/day

**For PhD research**: 5.75 days can write 2-3 paper sections. ALWAYS worth it.

---

## 🚀 QUICK START - Ready to Buy

### Before You Click "Launch"

**Pre-flight checklist** (2 min):
- [ ] AWS account active
- [ ] EC2 key pair created
- [ ] Security group allows SSH (port 22)
- [ ] S3 bucket created
- [ ] Know your AWS access keys

**Files ready**:
- ✅ `scripts/step3_effect_estimation_lasso.py` - Enhanced with resume + AWS SPOT handling
- ✅ `AWS_DEPLOYMENT_PLAN.md` - Complete guide (updated with correct costs)
- ✅ `QUICK_LAUNCH_GUIDE.md` - Step-by-step commands

---

## 💰 Exact Cost Breakdown

```
Instance: c7i.48xlarge SPOT
  - On-Demand rate: $9.65/hour
  - SPOT rate (typical): $2.90/hour (70% discount)
  - SPOT rate (worst case): $4.83/hour (50% discount)

Runtime: 11 hours (129,989 edges @ 235 edges/min)

Cost Calculation:
  - Instance: $2.90/hr × 11 hrs = $31.90
  - EBS storage (100 GB, 1 day): $0.27
  - Data transfer (S3): $0.09

TOTAL: $32.26

Worst case (SPOT price spike):
  - Instance: $4.83/hr × 11 hrs = $53.13
  - Storage + transfer: $0.36
  - TOTAL: $53.49

On-Demand (guaranteed):
  - Instance: $9.65/hr × 11 hrs = $106.15
  - Storage + transfer: $0.36
  - TOTAL: $106.51
```

**Recommendation**: Use SPOT ($32). Rare to get interrupted for <24 hr jobs.

---

## 📋 Launch Procedure (Copy-Paste Ready)

### Step 1: Package Local Files (5 min)

```bash
cd <repo-root>/v2.0/phaseA/A4_effect_quantification

# Create requirements file
cat > requirements.txt <<EOF
numpy>=1.24.0
pandas>=2.0.0
scikit-learn>=1.3.0
joblib>=1.3.0
psutil>=5.9.0
requests>=2.31.0
EOF

# Package code and data
tar -czf A4_package.tar.gz \
  scripts/ \
  requirements.txt \
  outputs/parent_adjustment_sets.pkl \
  ../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl

# Upload to S3 (replace YOUR-BUCKET)
aws s3 cp A4_package.tar.gz s3://YOUR-BUCKET/A4/
aws s3 cp requirements.txt s3://YOUR-BUCKET/A4/
```

### Step 2: Launch SPOT Instance via AWS Console (10 min)

**Easiest method**: Use AWS Console

1. Go to EC2 → Spot Requests → Request Spot Instances
2. **Instance type**: c7i.48xlarge
3. **AMI**: Amazon Linux 2023 (ami-0c55b159cbfafe1f0)
4. **Max price**: $4.83/hour (50% of on-demand)
5. **Storage**: 100 GB gp3
6. **Key pair**: Select your key
7. **Security group**: Allow SSH (port 22)
8. Click "Launch"

**Wait 2-3 minutes** for instance to start. Note the public IP.

### Step 3: SSH and Setup (10 min)

```bash
# SSH into instance
ssh -i ~/.ssh/YOUR-KEY.pem ec2-user@YOUR-INSTANCE-IP

# Install Python
sudo yum install -y python3.11 python3.11-pip tmux htop

# Download code
aws s3 cp s3://YOUR-BUCKET/A4/A4_package.tar.gz .
tar -xzf A4_package.tar.gz

# Install dependencies
pip3.11 install --user -r requirements.txt

# Create directories
mkdir -p logs checkpoints outputs
```

### Step 4: Run Quick Test (5 min)

```bash
# Test with 20 edges
python3.11 scripts/step3_effect_estimation_lasso.py \
  --sample_size 20 \
  --n_jobs 192 \
  --bootstrap 50

# Verify:
# - Completes in ~1 minute
# - No errors
# - Shows clean logs (no warnings)
# - "Final validated edges: X"
```

### Step 5: Launch Full Run in tmux (1 min)

```bash
# Start tmux (survives disconnect)
tmux new -s A4

# Launch full run
python3.11 scripts/step3_effect_estimation_lasso.py \
  --n_jobs 192 \
  --bootstrap 100 \
  --effect_threshold 0.12 \
  --checkpoint_every 5000 \
  | tee logs/step3_full_run.log

# Detach from tmux: Ctrl+B, then D
```

### Step 6: Monitor Progress (Every 2-3 Hours)

```bash
# SSH back in
ssh -i ~/.ssh/YOUR-KEY.pem ec2-user@YOUR-INSTANCE-IP

# Reattach to tmux
tmux attach -t A4

# Check latest progress
tail -30 logs/step3_full_run.log | grep "INFO"

# Expected output:
# ✅ Chunk complete: 50000/129989 (38.5%)
# Rate: 3.92 edges/sec (235 edges/min)
# ETA: 5.6 hours
```

### Step 7: Download Results & Terminate (10 min)

**Once complete** (you'll see "COMPLETE" in logs):

```bash
# Compress results
tar -czf A4_results.tar.gz \
  outputs/lasso_effect_estimates.pkl \
  checkpoints/ \
  logs/step3_full_run.log

# Upload to S3
aws s3 cp A4_results.tar.gz s3://YOUR-BUCKET/A4/results/

# Download locally
aws s3 cp s3://YOUR-BUCKET/A4/results/A4_results.tar.gz \
  <repo-root>/v2.0/phaseA/A4_effect_quantification/

# 🚨 CRITICAL: Terminate instance IMMEDIATELY
# Get instance ID from AWS Console, then:
aws ec2 terminate-instances --instance-ids i-XXXXX

# Or use console: EC2 → Instances → Select → Actions → Terminate
```

**Saves $2.90/hour** - Don't forget this step!

---

## ⏱️ Timeline

```
Hour 0:00 - Launch instance, setup (20 min hands-on)
Hour 0:20 - Start full run
Hour 0:41 - First checkpoint (5K edges)
Hour 4:38 - Halfway point (65K edges)
Hour 9:17 - 100K edges done
Hour 11:00 - COMPLETE ✅

Total hands-on time: ~1 hour (setup + monitoring)
Total wall time: ~11 hours
```

---

## 🔒 Safety Features (All Implemented)

✅ **Checkpoints every 5K edges** - Max 21 min loss on interruption
✅ **Resume capability** - `--resume checkpoint.pkl` flag
✅ **AWS SPOT interruption handler** - 2-min warning detection
✅ **Clean logs** - Warnings suppressed in worker processes
✅ **Progress tracking** - `verbose=10` shows completion %
✅ **Auto-save on exit** - Checkpoints save before termination

---

## 🆘 Failure Modes & Recovery

### If SPOT Interrupted Mid-Run

```bash
# Checkpoints are already saved to EBS
# Just launch new SPOT instance and:

# 1. Download latest checkpoint
latest=$(ls -t checkpoints/effect_estimation_checkpoint_*.pkl | head -1)

# 2. Resume
python3.11 scripts/step3_effect_estimation_lasso.py \
  --n_jobs 192 \
  --bootstrap 100 \
  --resume $latest \
  | tee -a logs/step3_full_run_resumed.log

# Max loss: 21 minutes, $1.02
```

### If You Lose SSH Connection

```bash
# Just SSH back in
ssh -i ~/.ssh/YOUR-KEY.pem ec2-user@YOUR-INSTANCE-IP

# Reattach to tmux
tmux attach -t A4

# Job keeps running even if you disconnect!
```

---

## ✅ Verification After Completion

```bash
# Extract results
tar -xzf A4_results.tar.gz

# Check output
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
```
Total edges: 129,989
Validated: ~93,000 (72%)
Mean effect size: 0.30-0.40
Mean controls: 6-15
```

---

## 📝 What to Tell Your Advisor

> "I'm running the effect estimation on AWS to save 6 days of local compute time. It'll cost $32 for an 11-hour run on a 192-core instance. The alternative is tying up my local machine for 6 days. I've implemented checkpointing every 21 minutes, so the max loss on any interruption is negligible. Results will be ready by end of day."

**Sounds professional, cost-conscious, and technically competent.** ✅

---

## 🎯 Decision Time

**Are you ready to spend $32 to save 5.75 days?**

- **YES** → Follow steps above, buy instance now
- **NO** → Use local (free, 6 days) - see QUICK_LAUNCH_GUIDE.md
- **UNSURE** → Read AWS_DEPLOYMENT_PLAN.md for full details

**For PhD research**: The answer is almost always YES. Time >> Money.

---

## 📚 Reference Files

- **This file**: Quick launch checklist
- **AWS_DEPLOYMENT_PLAN.md**: Complete 21-page guide with all details
- **QUICK_LAUNCH_GUIDE.md**: Side-by-side local vs AWS commands
- **A4_PHASE3_TEST_RESULTS.md**: Test validation results

---

**Status**: 🚀 READY TO LAUNCH

**Next action**: Copy commands above and start!

**Estimated completion**: 11 hours from launch

**Total cost**: $32

**Time saved**: 5.75 days

**ROI**: If your time is worth >$5.57/day, this is a no-brainer.

---

🚀 **GO LAUNCH YOUR INSTANCE!** 🚀
