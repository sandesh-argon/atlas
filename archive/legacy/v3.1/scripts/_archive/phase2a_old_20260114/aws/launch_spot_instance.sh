#!/bin/bash
# Launch AWS spot instance for country SHAP computation
# Usage: ./launch_spot_instance.sh [instance-number] [country-range]
# Example: ./launch_spot_instance.sh 1 A-D

set -e

INSTANCE_NUM=${1:-1}
COUNTRY_RANGE=${2:-"A-D"}
INSTANCE_TYPE="c7i.8xlarge"  # 32 vCPUs
AMI_ID="ami-0c7217cdde317cfec"  # Ubuntu 22.04 us-east-1
KEY_NAME="Final"
SECURITY_GROUP="sg-0a1b2c3d4e5f6g7h8"  # Update with your SG

echo "=== Launching Spot Instance #${INSTANCE_NUM} for ${COUNTRY_RANGE} ==="

# Request spot instance
SPOT_REQUEST=$(aws ec2 request-spot-instances \
    --instance-count 1 \
    --type "one-time" \
    --launch-specification "{
        \"ImageId\": \"${AMI_ID}\",
        \"InstanceType\": \"${INSTANCE_TYPE}\",
        \"KeyName\": \"${KEY_NAME}\",
        \"BlockDeviceMappings\": [{
            \"DeviceName\": \"/dev/sda1\",
            \"Ebs\": {
                \"VolumeSize\": 100,
                \"VolumeType\": \"gp3\",
                \"DeleteOnTermination\": false
            }
        }]
    }" \
    --query 'SpotInstanceRequests[0].SpotInstanceRequestId' \
    --output text)

echo "Spot request ID: ${SPOT_REQUEST}"
echo "Waiting for instance to launch..."

# Wait for spot request to be fulfilled
aws ec2 wait spot-instance-request-fulfilled --spot-instance-request-ids ${SPOT_REQUEST}

# Get instance ID
INSTANCE_ID=$(aws ec2 describe-spot-instance-requests \
    --spot-instance-request-ids ${SPOT_REQUEST} \
    --query 'SpotInstanceRequests[0].InstanceId' \
    --output text)

echo "Instance ID: ${INSTANCE_ID}"

# Wait for instance to be running
aws ec2 wait instance-running --instance-ids ${INSTANCE_ID}

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids ${INSTANCE_ID} \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo "Public IP: ${PUBLIC_IP}"

# Tag the instance
aws ec2 create-tags --resources ${INSTANCE_ID} \
    --tags Key=Name,Value="v31-country-shap-${COUNTRY_RANGE}" \
           Key=Project,Value="v3.1" \
           Key=CountryRange,Value="${COUNTRY_RANGE}"

# Ensure EBS survives termination
aws ec2 modify-instance-attribute --instance-id ${INSTANCE_ID} \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"DeleteOnTermination":false}}]'

echo ""
echo "=== Instance Ready ==="
echo "Instance ID: ${INSTANCE_ID}"
echo "Public IP: ${PUBLIC_IP}"
echo "Country Range: ${COUNTRY_RANGE}"
echo ""
echo "Next steps:"
echo "  1. Run: ./setup_instance.sh ${PUBLIC_IP} ${COUNTRY_RANGE}"
echo "  2. Start sync: ./sync_country_shap.sh ${PUBLIC_IP} ${COUNTRY_RANGE}"
echo ""

# Save instance info
echo "${INSTANCE_ID},${PUBLIC_IP},${COUNTRY_RANGE}" >> instances.csv
