import subprocess
import time

class VastAIManager():
    def __init__(self):
        self.instances = []
        self.instancesToContractMapping = {}
        self.templateID = 'cec5ce148a81303ca541bc479eace67b'
        self.baseCommand = "wsl -d Ubuntu-20.04 exec /home/Neuralperk/Neuralperk_Env/bin/vastai" # Windows Base Command
        # self.baseCommand = "/home/Neuralperk/Neuralperk_Env/bin/vastai" # Linux Base Command  
    
    def getFinalCommand(self, command):
        return self.baseCommand + " " + command

    def createInstance(self, instanceID):
        command = f'create instance --template {self.templateID} {instanceID} --image nicky9319/neuralperk:latest --disk 32'
        finalComamnd = self.getFinalCommand(command)
        response = subprocess.run(finalComamnd, capture_output=True, text=True)
        result = response.stdout

        spawnInstance = str(result)

        dictStartIndex = spawnInstance.find("{")
        dictEndIndex = spawnInstance.rfind("}") + 1

        spawnInstance = spawnInstance[dictStartIndex:dictEndIndex]   
        spawnInstance = eval(spawnInstance)     
        contractID = spawnInstance['new_contract']
        self.instancesToContractMapping[instanceID] = contractID

        self.instances.append(instanceID)

        return result

    def destroyInstance(self, instanceID):
        contractId = self.instancesToContractMapping[instanceID]
        command = f'destroy instances "{contractId}"'
        finalComamnd = self.getFinalCommand(command)

        self.instances.remove(instanceID)
        self.instancesToContractMapping.pop(instanceID)

        print(finalComamnd)

        response = subprocess.run(finalComamnd, capture_output=True, text=True)
        result = response.stdout
        return result

    def listInstances(self , filter = None):
        command = 'search offers "cuda_vers >= 12.5 num_gpus=1 gpu_name=RTX_3090 gpu_ram>=8 rented=False"'

        if filter is not None:
            basicCommands = 'search offers'
            filteringParamCommands = '"' +  ' '.join(filter) + '"'
            command = basicCommands + " " + filteringParamCommands


        finalComamnd = self.getFinalCommand(command)

        response = subprocess.run(finalComamnd, capture_output=True, text=True)
        result = response.stdout
        result = result.split('\n')[1:-1]

        InstancesInfoList = [[row.split()[0] , row.split()[3] , row.split()[9] , row.split()[19] , row.split()[22]] for row in result]
        return InstancesInfoList

    def checkInstanceInUse(self, instanceID):
        if instanceID in self.instances:
            return True
        
        return False

    def checkInstanceAvailableForUse(self, instanceID):
        command = f'search offers "ask_contract_id == {instanceID}"'
        finalComamnd = self.getFinalCommand(command)

        response = subprocess.run(finalComamnd, capture_output=True, text=True)
        result = response.stdout

        result = str(result)

        return len(result.split('\n')) > 2
        




vastAiManager = VastAIManager()
filters = ["cuda_vers >= 12.5","num_gpus=1","gpu_name=RTX_3080","gpu_ram>=8"]
# output = vastAiManager.listInstances(filter=filters)
# output = vastAiManager.listInstances()

print(vastAiManager.checkInstanceAvailableForUse("13109400"))



