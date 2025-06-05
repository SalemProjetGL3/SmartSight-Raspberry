#!/bin/bash

echo "Starting Raspberry Pi 5 CV/MQTT Publisher Setup for YOLO NAS S + MIDAS..."


#download mosquito if not already installed
if ! command -v mosquitto &> /dev/null; then
    echo "Mosquitto not found, installing..."
    sudo apt install -y mosquitto mosquitto-clients
    # Configure Mosquitto to allow anonymous access and on 0.0.0.0 (for testing purposes)
    sudo bash -c 'cat > /etc/mosquitto/conf.d/custom.conf << EOF
    listener 1883 0.0.0.0
    allow_anonymous true
    EOF'
else
    echo "Mosquitto is already installed."
fi 



# Enable and start Mosquitto service
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
# Check if Mosquitto is running
if systemctl is-active --quiet mosquitto; then
    echo "Mosquitto service is running."
else
    echo "Failed to start Mosquitto service. Please check the logs."
    exit 1
fi

# Update and Upgrade system packages
sudo apt update
sudo apt upgrade -y

# Install Python and Pip (usually pre-installed on Raspberry Pi OS)
sudo apt install -y python3 python3-pip python3-dev python3-venv


# Install libcamera and Picamera2 for the Sony IMX708 camera
sudo apt install -y python3-picamera2 --no-install-recommends

# Install system dependencies for OpenCV and other packages
sudo apt install -y libatlas-base-dev libhdf5-dev libhdf5-serial-dev libatlas3-base libjasper-dev libqtgui4 libqt4-test

# Create virtual environment (recommended for Python packages)
python3 -m venv ~/cv_env
source ~/cv_env/bin/activate

# Upgrade pip in virtual environment  
pip install --upgrade pip

# Install packages from requirements.txt
if [ -f "requirements.txt" ]; then
    echo "Installing Python packages from requirements.txt..."
    pip install -r requirements.txt
else
    echo "requirements.txt not found! Please create it first."
    exit 1
fi

echo "------------------------------------------------------------------"
echo "Setup completed successfully!"
echo ""
echo "To activate the virtual environment in future sessions:"
echo "source ~/cv_env/bin/activate"
echo ""
echo "Next steps:"
echo "1. Ensure your MQTT broker is running and accessible"
echo "2. Update BROKER_ADDRESS in publisher.py if needed"
echo "3. Test the camera connection"
echo "4. Run: python3 publisher.py"
echo "------------------------------------------------------------------"