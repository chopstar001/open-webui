#!/bin/bash

# Open WebUI Docker Container Restart Script

CONTAINER_NAME="open-webui"
HOST_PORT=3000

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Restarting Open WebUI Docker container...${NC}"

# Check if container exists
if [ "$(docker ps -a -q -f name=$CONTAINER_NAME)" ]; then
    echo -e "${YELLOW}Stopping container...${NC}"
    docker stop $CONTAINER_NAME
    
    echo -e "${YELLOW}Starting container...${NC}"
    docker start $CONTAINER_NAME
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Container restarted successfully!${NC}"
        echo -e "Web UI: ${GREEN}http://localhost:${HOST_PORT}${NC}"
    else
        echo -e "${RED}Failed to start container.${NC}"
        exit 1
    fi
else
    echo -e "${RED}Container '$CONTAINER_NAME' does not exist.${NC}"
    echo -e "${YELLOW}Use ./run.sh to create it first.${NC}"
    exit 1
fi

echo -e "\n${GREEN}Container restarted and ready!${NC}"
