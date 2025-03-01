# Mention the Files you want to transfer to the Remote Server alongiside with the Remote Server IP Address and the Remote Server Directory

# Example: 
scp -r Logging/ \
    ServiceTemplates/ \
    ServicesSetupFiles/ \
    ServiceURLMapping.json \
    requirements.txt \
    .env \
    ServerScripts/ \
    \
    service_CommunicationInterface/ \
    service_CredentialServer/ \
    service_CustomerServer/ \
    service_SessionSupervisor/ \
    service_UserHTTPserver/ \
    service_UserManager/ \
    service_UserWSserver/ \
    \
    # paarth@167.71.239.193:/home/paarth/MainServer/