# ✅ AWS DEPLOYMENT - READY TO LAUNCH

**Date**: November 17, 2025
**Status**: All scripts created and ready for validation
**Next Action**: Run local validation tests, then launch AWS

---

## 📦 Files Created

### Core Scripts ✅
1. **`scripts/step2b_full_backdoor_test.py`** - Local validation (test 100 edges)
2. **`scripts/step2b_full_backdoor_adjustment.py`** - Production AWS script (192 cores)

### Utilities ✅
3. **`scripts/utils/verify_dependencies.py`** - Check all packages installed
4. **`scripts/utils/thermal_monitor.py`** - Monitor CPU temperatures
5. **`scripts/utils/email_alerts.py`** - Email notifications for progress/completion

### Documentation ✅
6. **`CRITICAL_FINDING_PARENT_ADJUSTMENT.md`** - Methodology decision analysis
7. **`outputs/parent_adjustment_sets.pkl`** - Parent sets (backup if needed)

---

## 🧪 VALIDATION TESTS (Run Locally BEFORE AWS)

### Test 1: Verify Dependencies (2 min)
```bash
cd <repo-root>/v2.0/phaseA/A4_effect_quantification

python scripts/utils/verify_dependencies.py
```

**Expected**: All packages show ✅
**If failures**: Run `pip install <missing-package>`

---

### Test 2: Test 100 Edges (20-30 min)
```bash
python scripts/step2b_full_backdoor_test.py \
  --input ../A3_conditional_independence/outputs/A3_final_dag_v2.pkl \
  --n_edges 100 \
  --cores 10 \
  --output tests/backdoor_test_100.pkl
```

**Expected Output**:
```
✅ TEST COMPLETE
Edges tested: 100
Successful: 95-100 (95-100%)
Mean backdoor size: 40-45 variables
Mean time per edge: 12-16 seconds

AWS Projection (192 cores):
  Estimated time: 30-36 hours
  Estimated cost: $73-$88
```

**If test fails**: Debug locally before AWS deployment

---

### Test 3: Checkpoint Functionality (10 min)
```bash
# Start test with checkpointing
python scripts/step2b_full_backdoor_test.py \
  --n_edges 50 \
  --cores 10 \
  --checkpoint_every 25 \
  --output tests/checkpoint_test.pkl

# Manually kill after checkpoint 1 (Ctrl+C after ~25 edges)

# Resume from checkpoint
python scripts/step2b_full_backdoor_test.py \
  --resume tests/checkpoint_test_checkpoint_25.pkl \
  --cores 10
```

**Expected**: Resumes from edge 26, completes remaining 25
**If resume fails**: Fix before AWS (resume critical for spot instances)

---

### Test 4: Thermal Monitor (5 min)
```bash
python scripts/utils/thermal_monitor.py \
  --temp_limit 85 \
  --duration 300
```

**Expected**: Reports CPU temps every 30s
**Note**: On AWS this won't apply (cloud instances don't overheat)

---

## 📋 AWS DEPLOYMENT CHECKLIST

### Pre-Flight (Do AFTER local tests pass) ✅
- [ ] All 4 validation tests passed locally
- [ ] AWS account created + payment method added
- [ ] Budget alert set ($100 limit)
- [ ] SSH key pair generated (`~/.ssh/aws_key.pem`)
- [ ] Email alerts configured (optional):
  ```bash
  export EMAIL_USER="your-email@gmail.com"
  export EMAIL_PASSWORD="your-gmail-app-password"
  export EMAIL_RECIPIENT="your-email@gmail.com"
  ```

### Launch Instance (USER TASK)
- [ ] Launch c7i.48xlarge spot instance
  - **Region**: us-east-1 (cheapest)
  - **AMI**: Ubuntu 22.04 LTS
  - **Max Price**: $2.50/hour (market price ~$2.45)
  - **Storage**: 100 GB gp3 EBS
  - **Security Group**: Allow SSH (port 22) from your IP
- [ ] Get instance public IP/DNS
- [ ] SSH connection verified

### Environment Setup on AWS (30 min)
```bash
# SSH into instance
ssh -i ~/.ssh/aws_key.pem ubuntu@<AWS_IP>

# Install dependencies
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3.11 python3.11-venv python3-pip tmux

# Create virtual environment
python3.11 -m venv ~/venv
source ~/venv/bin/activate

# Install packages (10-15 min)
pip install --upgrade pip
pip install numpy pandas scipy scikit-learn networkx statsmodels joblib tqdm psutil requests
```

### Transfer Code to AWS (10 min)
```bash
# On LOCAL machine:
cd <repo-root>/v2.0/phaseA

# Create deployment package
tar -czf a4_deployment.tar.gz \
  A4_effect_quantification/scripts/ \
  A3_conditional_independence/outputs/A3_final_dag_v2.pkl

# Transfer to AWS
scp -i ~/.ssh/aws_key.pem a4_deployment.tar.gz ubuntu@<AWS_IP>:~/

# On AWS instance:
cd ~
tar -xzf a4_deployment.tar.gz

# Verify files
ls -lh A3_conditional_independence/outputs/A3_final_dag_v2.pkl
ls -lh A4_effect_quantification/scripts/
```

### Validation on AWS (20 min)
```bash
# On AWS instance:
cd ~/A4_effect_quantification
source ~/venv/bin/activate

# Test 1000 edges to estimate runtime
python scripts/step2b_full_backdoor_test.py \
  --input ~/A3_conditional_independence/outputs/A3_final_dag_v2.pkl \
  --n_edges 1000 \
  --cores 192 \
  --output tests/aws_test_1000.pkl

# Expected: 1000 edges complete in 10-15 minutes
# If >20 minutes: Something wrong (network I/O, parallelization)
```

---

## 🚀 PRODUCTION RUN (32 hours)

### Launch Job
```bash
# Start tmux session (CRITICAL - prevents SSH disconnection)
tmux new -s backdoor

# Inside tmux:
cd ~/A4_effect_quantification
source ~/venv/bin/activate

# Set email alerts (optional)
export EMAIL_USER="your-email@gmail.com"
export EMAIL_PASSWORD="your-app-password"
export EMAIL_RECIPIENT="your-email@gmail.com"

# Launch production run
python scripts/step2b_full_backdoor_adjustment.py \
  --input ~/A3_conditional_independence/outputs/A3_final_dag_v2.pkl \
  --output ~/outputs/full_backdoor_sets.pkl \
  --cores 192 \
  --checkpoint_every 5000 \
  --log_every 100 \
  2>&1 | tee logs/production_run.log

# Detach from tmux: Ctrl+B, then D
# Reattach later: tmux attach -t backdoor
```

### Monitor Progress

**From local machine**:
```bash
# View live log
ssh -i ~/.ssh/aws_key.pem ubuntu@<AWS_IP> "tail -f ~/A4_effect_quantification/logs/production_run.log"

# Check progress (every hour)
ssh -i ~/.ssh/aws_key.pem ubuntu@<AWS_IP> "grep 'Progress:' ~/A4_effect_quantification/logs/production_run.log | tail -5"
```

**Expected output every ~1 minute**:
```
[2025-11-17 15:32:15] Progress: 12,400 / 129,989 (9.5%) | Rate: 10.2 edges/sec | ETA: 30.8 hours
[2025-11-17 15:33:16] Progress: 12,612 / 129,989 (9.7%) | Rate: 10.3 edges/sec | ETA: 30.6 hours
```

**Checkpoints saved every 45-60 minutes** at `~/A4_effect_quantification/checkpoints/`

---

## 📥 DOWNLOAD RESULTS (After 32 hours)

```bash
# Check completion
ssh -i ~/.ssh/aws_key.pem ubuntu@<AWS_IP> "tail ~/A4_effect_quantification/logs/production_run.log"

# Look for:
# ✅ PRODUCTION RUN COMPLETE
# Edges processed: 129,989
# Runtime: 32.1 hours

# Download results
scp -i ~/.ssh/aws_key.pem \
  ubuntu@<AWS_IP>:~/outputs/full_backdoor_sets.pkl \
  <repo-root>/v2.0/phaseA/A4_effect_quantification/outputs/

# Download logs (backup)
scp -i ~/.ssh/aws_key.pem \
  ubuntu@<AWS_IP>:~/A4_effect_quantification/logs/production_run.log \
  <repo-root>/v2.0/phaseA/A4_effect_quantification/logs/
```

### Verify Results Locally
```bash
cd <repo-root>/v2.0/phaseA/A4_effect_quantification

python -c "
import pickle
with open('outputs/full_backdoor_sets.pkl', 'rb') as f:
    data = pickle.load(f)

print(f'Edges processed: {len(data[\"edges\"])}')
print(f'Mean backdoor size: {data[\"metadata\"][\"mean_backdoor_size\"]}')
print(f'Runtime: {data[\"metadata\"][\"runtime_hours\"]} hours')
"

# Expected:
# Edges processed: 129989
# Mean backdoor size: 42.3
# Runtime: 32.1 hours
```

---

## 🛑 TERMINATE AWS INSTANCE (CRITICAL)

```bash
# Get instance ID
aws ec2 describe-instances \
  --filters "Name=instance-state-name,Values=running" \
  --query "Reservations[*].Instances[*].InstanceId"

# Terminate
aws ec2 terminate-instances --instance-ids i-xxxxxxxxx

# Or use AWS Console:
# EC2 Dashboard → Instances → Select instance → Actions → Terminate
```

**Verify termination**:
- AWS Console → EC2 → Instances → Status: "Terminated"
- Billing Dashboard → Cost stops accumulating

**Expected cost**: ~$78-$88 for 32-36 hours @ $2.45/hour

---

## ⚠️ IF THINGS GO WRONG

### Spot Instance Interrupted Mid-Run
**Symptom**: SSH disconnects, instance terminated by AWS

**Solution**:
1. Last checkpoint saved to `~/checkpoints/`
2. Launch new spot instance (same steps)
3. Transfer checkpoint from old EBS volume or S3
4. Resume:
   ```bash
   python scripts/step2b_full_backdoor_adjustment.py \
     --resume ~/checkpoints/backdoor_checkpoint_65000.pkl \
     --cores 192
   ```

### Job Slower Than Expected
**Symptom**: After 4 hours, ETA shows >50 hours

**Diagnosis**:
- Check CPU usage: Should be ~95-98%
  ```bash
  ssh ubuntu@<AWS_IP> "top -bn1 | grep 'Cpu'"
  ```
- If CPU <80%: Network I/O bottleneck or poor parallelization

**Solutions**:
- Increase instance type to c7i.metal-48xl (dedicated hardware)
- OR split job: Run 0-65K and 65K-130K separately

### Out of Memory
**Symptom**: Process killed with "Killed" message

**Solution**:
- Reduce `--cores` from 192 to 96 (uses less memory)
- OR upgrade to r7i.48xlarge (384 GB → 768 GB RAM)

---

## 📊 COST TRACKING

**Estimated**:
- Instance runtime: 32-36 hours
- Hourly rate: $2.45/hour
- **Total: $78-$88**

**Monitor in real-time**:
- AWS Console → Billing → Cost Explorer
- Set budget alert at $100 (safety margin)

---

## 🎯 NEXT STEPS AFTER COMPLETION

1. ✅ Download `full_backdoor_sets.pkl` to local machine
2. ✅ Verify results (129,989 edges, mean ~42 variables)
3. ✅ Terminate AWS instance
4. ✅ Verify final cost (~$80)
5. → **Proceed to A4 Phase 3: Effect Estimation**

---

**Status**: ⏳ Awaiting local validation tests
**Action Required**: Run Test 1-4 above, verify all pass, then proceed to AWS launch

---

**Created**: November 17, 2025 15:00
**Scripts Location**: `<repo-root>/v2.0/phaseA/A4_effect_quantification/scripts/`
