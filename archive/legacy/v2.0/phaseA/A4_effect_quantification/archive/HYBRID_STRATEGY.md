# Hybrid Strategy: Start Local, Switch to AWS When Approved

**Date**: November 17, 2025
**Status**: 🔄 QUOTA INCREASE PENDING

---

## 📋 Situation

**AWS Quota Status**: Requested c7i.48xlarge SPOT quota increase
**Approval Time**: 48 hours to several days
**Strategy**: Start local NOW, switch to AWS when approved

---

## 🎯 Why This Works Perfectly

### Checkpoint System Enables Seamless Transfer

**Local run configuration**:
```bash
--n_jobs 10
--checkpoint_every 5000
```

**Checkpoints saved every**: ~6 hours (5,000 edges @ 14.7 edges/min = 340 min)

**Transfer points**:
- After 5K edges: ~6 hours local → Resume on AWS (saves 5.5 days)
- After 10K edges: ~12 hours local → Resume on AWS (saves 5.4 days)
- After 25K edges: ~1.2 days local → Resume on AWS (saves 4.5 days)
- After 50K edges: ~2.3 days local → Resume on AWS (saves 3.5 days)

**Key insight**: You can switch at ANY checkpoint with ZERO work lost!

---

## 🚀 Phase 1: Local Run (Starting Now)

### Launch Command

```bash
cd <repo-root>/v2.0/phaseA/A4_effect_quantification

# Clean environment
pkill -9 -f "step3_effect_estimation"
pkill -9 -f "step2_backdoor"
pkill -9 -f "loky.backend"
ps aux | grep -E "(step|loky)" | grep -v grep  # Should show 0

# Launch with AWS-compatible settings
nohup python scripts/step3_effect_estimation_lasso.py \
  --n_jobs 10 \
  --bootstrap 100 \
  --effect_threshold 0.12 \
  --checkpoint_every 5000 \
  > logs/step3_local_run.log 2>&1 &

# Save PID
echo $! > logs/step3_local_pid.txt
```

### Monitor Progress

```bash
# Check progress (every 4-6 hours)
tail -50 logs/step3_local_run.log | grep "INFO"

# Expected checkpoints:
# Hour 6: checkpoint_5000.pkl (3.8% done)
# Hour 12: checkpoint_10000.pkl (7.7% done)
# Hour 29: checkpoint_25000.pkl (19.2% done)
# Hour 57: checkpoint_50000.pkl (38.5% done)
# Hour 113: checkpoint_100000.pkl (76.9% done)
# Hour 147: COMPLETE (100%)
```

### Checkpoints Location

```bash
ls -lh checkpoints/

# Expected files:
# effect_estimation_checkpoint_5000.pkl
# effect_estimation_checkpoint_10000.pkl
# effect_estimation_checkpoint_15000.pkl
# ...
```

---

## 🔄 Phase 2: Switch to AWS (When Quota Approved)

### Decision Point: When to Switch

**Calculate remaining time vs AWS setup overhead**:

```python
# Quick calculator
edges_done = 25000  # Current checkpoint
edges_remaining = 129989 - edges_done
local_rate = 14.7  # edges/min
aws_rate = 235  # edges/min

local_hours_remaining = (edges_remaining / local_rate) / 60
aws_hours_remaining = (edges_remaining / aws_rate) / 60
aws_setup_hours = 1  # Setup + transfer time

time_saved = local_hours_remaining - (aws_hours_remaining + aws_setup_hours)

print(f"Local remaining: {local_hours_remaining:.1f} hours")
print(f"AWS remaining: {aws_hours_remaining + aws_setup_hours:.1f} hours")
print(f"Time saved by switching: {time_saved:.1f} hours")
print(f"Worth switching: {time_saved > 2}")  # If saves >2 hours
```

**Switch if**:
- Time saved > 2 hours (worth the overhead)
- You're at ≤100K edges done (~77% complete)

**Don't switch if**:
- >100K edges done (almost finished anyway)
- Time saved < 2 hours

### Step-by-Step Transfer

#### 1. Stop Local Run (1 min)

```bash
# Get PID
cat logs/step3_local_pid.txt

# Kill gracefully (checkpoint will save)
kill <PID>

# Or force kill all
pkill -9 -f "step3_effect_estimation"
pkill -9 -f "loky.backend"

# Wait 30 seconds for checkpoint to save
sleep 30

# Verify latest checkpoint
ls -lht checkpoints/ | head -3
```

#### 2. Package and Upload (5 min)

```bash
# Package checkpoint and dependencies
tar -czf A4_transfer.tar.gz \
  checkpoints/ \
  scripts/ \
  outputs/parent_adjustment_sets.pkl \
  ../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl \
  requirements.txt

# Upload to S3
aws s3 cp A4_transfer.tar.gz s3://YOUR-BUCKET/A4/transfer/

# Note which checkpoint to resume from
latest_checkpoint=$(ls -t checkpoints/effect_estimation_checkpoint_*.pkl | head -1)
echo "Resume from: $latest_checkpoint" > resume_info.txt
aws s3 cp resume_info.txt s3://YOUR-BUCKET/A4/transfer/
```

#### 3. Launch AWS Instance (10 min)

Follow `READY_TO_BUY_INSTANCE.md` Steps 2-3:
- Launch c7i.48xlarge SPOT via console
- SSH in
- Install Python 3.11

#### 4. Download and Resume (5 min)

```bash
# On AWS instance:
aws s3 cp s3://YOUR-BUCKET/A4/transfer/A4_transfer.tar.gz .
aws s3 cp s3://YOUR-BUCKET/A4/transfer/resume_info.txt .

# Extract
tar -xzf A4_transfer.tar.gz

# Install dependencies
pip3.11 install --user -r requirements.txt

# Check which checkpoint to resume from
cat resume_info.txt

# Find latest checkpoint
latest=$(ls -t checkpoints/effect_estimation_checkpoint_*.pkl | head -1)
echo "Resuming from: $latest"

# Start in tmux
tmux new -s A4

# Resume from checkpoint
python3.11 scripts/step3_effect_estimation_lasso.py \
  --n_jobs 192 \
  --bootstrap 100 \
  --effect_threshold 0.12 \
  --checkpoint_every 5000 \
  --resume $latest \
  | tee logs/step3_aws_resumed.log

# Detach: Ctrl+B, then D
```

#### 5. Verify Resume Worked (1 min)

```bash
# Check log
tail -50 logs/step3_aws_resumed.log | grep "INFO"

# Should see:
# 📂 Loading checkpoint: checkpoints/effect_estimation_checkpoint_25000.pkl
# ✅ Loaded 25,000 completed edges
# Resuming from edge 25,000
# Remaining edges: 104,989
#
# Processing at ~235 edges/min
```

---

## 💰 Cost Savings by Transfer Point

| Transfer Point | Edges Done | Local Time Used | AWS Time Needed | AWS Cost | Time Saved |
|----------------|------------|-----------------|-----------------|----------|------------|
| **5K (4%)** | 5,000 | 6 hours | 8.8 hours | $26 | 5.5 days |
| **10K (8%)** | 10,000 | 11 hours | 8.5 hours | $25 | 5.4 days |
| **25K (19%)** | 25,000 | 28 hours | 7.4 hours | $22 | 4.6 days |
| **50K (38%)** | 50,000 | 57 hours | 5.7 hours | $17 | 3.7 days |
| **65K (50%)** | 65,000 | 74 hours | 4.6 hours | $13 | 2.9 days |
| **100K (77%)** | 100,000 | 113 hours | 2.1 hours | $6 | 1.3 days |

**Sweet spot**: Transfer at 25K-50K edges (saves 3.5-4.5 days, costs $17-22)

---

## 📊 Progress Tracking

### Local Progress Milestones

```bash
# Create progress tracker
cat > check_progress.sh <<'EOF'
#!/bin/bash
latest_log=$(tail -50 logs/step3_local_run.log | grep "Chunk complete" | tail -1)
echo "Latest progress:"
echo "$latest_log"

latest_checkpoint=$(ls -t checkpoints/effect_estimation_checkpoint_*.pkl | head -1)
if [ -n "$latest_checkpoint" ]; then
    edges_done=$(echo $latest_checkpoint | grep -oP '\d+(?=\.pkl)')
    percent=$((edges_done * 100 / 129989))
    echo ""
    echo "Latest checkpoint: $latest_checkpoint"
    echo "Edges completed: $edges_done / 129,989 ($percent%)"

    # Estimate time to completion
    local_remaining=$((129989 - edges_done))
    local_hours=$((local_remaining * 60 / 14.7 / 60))
    aws_hours=$((local_remaining * 60 / 235 / 60))

    echo ""
    echo "If continuing local: ~$local_hours hours remaining"
    echo "If switching to AWS: ~$((aws_hours + 1)) hours remaining (+ 1hr setup)"
    echo "Time saved by switching: ~$((local_hours - aws_hours - 1)) hours"
fi
EOF

chmod +x check_progress.sh

# Run anytime
./check_progress.sh
```

### Email/Slack Notifications (Optional)

```bash
# Add to crontab to check every 6 hours
crontab -e

# Add line:
0 */6 * * * cd <repo-root>/v2.0/phaseA/A4_effect_quantification && ./check_progress.sh | mail -s "A4 Progress Update" your@email.com
```

---

## 🔧 Failure Modes During Hybrid

### If Local Crashes Before AWS Ready

```bash
# Find latest checkpoint
latest=$(ls -t checkpoints/effect_estimation_checkpoint_*.pkl | head -1)

# Clean processes
pkill -9 -f "step3_effect_estimation"
pkill -9 -f "loky.backend"

# Resume local
nohup python scripts/step3_effect_estimation_lasso.py \
  --n_jobs 10 \
  --bootstrap 100 \
  --resume $latest \
  >> logs/step3_local_run.log 2>&1 &
```

### If AWS Quota Never Approved

**No problem!** Local run continues to completion:
- Total time: 6 days
- Total cost: $0
- No work lost

### If AWS Quota Approved After 90% Local Complete

**Don't switch!**
- Local remaining: <15 hours
- AWS setup + run: ~3 hours
- Time saved: ~12 hours
- Not worth the transfer overhead at that point
- Just let local finish

---

## 📋 Decision Flowchart

```
AWS Quota Approved?
│
├─ No → Continue local (check every 12 hours)
│
└─ Yes → Check progress
    │
    ├─ <50K edges done (38%)?
    │   └─ SWITCH to AWS (saves 3.5+ days, $17+)
    │
    ├─ 50-100K edges done (38-77%)?
    │   └─ CALCULATE time saved
    │       ├─ >24 hours saved? → SWITCH
    │       └─ <24 hours saved? → Maybe continue local
    │
    └─ >100K edges done (77%)?
        └─ CONTINUE local (almost done anyway)
```

---

## ✅ Current Status: Local Run Starting

**Action taken**: Launching local run with AWS-compatible checkpointing

**Next check**: 6 hours (first checkpoint)

**AWS quota status**: Pending approval (48+ hours)

**Flexibility**: Can switch to AWS at ANY checkpoint when approved

---

## 📝 What to Tell Your Advisor

> "I'm running the effect estimation now. Started it locally while waiting for AWS quota approval (48+ hours). The code saves checkpoints every 6 hours, so when AWS gets approved, I can seamlessly transfer the workload and complete it 16× faster. If AWS never approves, the local run finishes in 6 days anyway. No downside to starting now."

**Shows**:
- Proactive (not waiting idle)
- Resourceful (hybrid strategy)
- Risk-aware (checkpointing = zero loss)
- Professional (planned for contingencies)

---

## 🎯 Summary

**Current plan**:
1. ✅ Local run starting NOW (10 cores, 5K checkpoints)
2. ⏳ AWS quota pending (48+ hours)
3. 🔄 Transfer when approved (saves 3-5 days, costs $15-25)
4. ✅ Zero work lost either way

**Best case**: AWS approved in 48 hours → Transfer at 25K edges → Save 4.5 days, cost $22
**Worst case**: AWS never approved → Local completes in 6 days → Cost $0

**Either way, you win!** 🚀
