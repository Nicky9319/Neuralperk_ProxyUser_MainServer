class UserDBManager():

    def __init__(self):
        from pymongo import MongoClient
        mongoClient = MongoClient('localhost', 27017)

        self.db = mongoClient['Users']
        

        
        # Collection References Section !!! ------------------------------------------------------------------------------------------------------------------------------

        self.CredentialCollection = self.db['Credentials']
        self.UEM_Collections= self.db['UUID_Email_Mapping']
        self.ActivityCollections= self.db['UserActivity']
        self.PaymentsCollections= self.db['Payments']
    
            
        # Collection References Section END !!! --------------------------------------------------------------------------------------------------------------------------




    # Basic DB Interactions Section !!! ------------------------------------------------------------------------------------------------------------------------------

    def CheckAndCreateNewUser(self, email, password):
        if self.CheckUserExist(email) == False:
           self.CreateNewUser(email, password)
        
        return 

    def CreateNewUser(self, email, password):
        self.credential_InsertNewUser(email, password)
        self.activity_CreateUserActivity(email)

    def CheckUserExist(self, email):
        if self.credential_GetUserInformation(email) == None:
            return False
        
        return True

    def GetUserFinancials(self, email):
        userInfo = self.credential_GetUserInformation(email)
        return {"TOTAL_EARNINGS": userInfo["TotalEarnings"], "BALANCE": userInfo["Balance"]}

    def WithdrawAmount(self, upiID, amount, email, addNote=""):
        if amount == 0:
            return 
        
        if amount > self.credential_GetUserBalance(email):
            return False

        self.credential_DecreaseUserBalance(email, amount)
        
        import datetime as dt
        date = dt.datetime.now().strftime("%d/%m/%Y")

        self.payments_InsertNewPayment(upiID, amount, email, date, addNote)
        return True

    # basic DB Interactions Section END !!! --------------------------------------------------------------------------------------------------------------------------






    # Credential Collection Section !!! ------------------------------------------------------------------------------------------------------------------------------


    # Basic Utility Functions !!! -------------------------------------------------------------------------------------------

    def credential_CreateWithdrawalObject(self, date, time, amount, upiID):
        return {"Date": date, "Time": time, "Amount": amount, "UpiID": upiID}

    def credential_CheckCredentials(self, email, password):
        if self.CheckUserExist(email) == False:
            return False
        
        retrivedPassword = self.credential_GetUserPassword(email)
        if(retrivedPassword == password):
            return True
        
        return False

    def credential_IncrementUserTotalEarningsAndBalance(self, email, amount):
        self.credential_UpdateUserTotalEarnings(email, self.credential_GetUserTotalEarnings(email) + amount)
        self.credential_UpdateUserBalance(email, self.credential_GetUserBalance(email) + amount)

    def credential_TotalTimeSpent(self, email):
        sessionList = self.activity_GetUserContainerSessions(email)
        hoursSpend = 0
        for session in sessionList:
            startTime = session['StartTime']
            endTime = session['EndTime']
            hoursSpend += self.credential_helper_CalculateTimeDifferenceInHours(startTime, endTime)
        
        # print(f"Hours Spend Before Stripping the Time to 2 decimal places : {hoursSpend}")

        def stripHoursSpendToTwoDecimal(number):
            return "{:.2f}".format(number)
        
        hoursSpend = stripHoursSpendToTwoDecimal(hoursSpend)
        # print(f"Hours Spend After Stripping the Time to 2 decimal places : {hoursSpend}")

        return hoursSpend

    def credential_DecreaseUserBalance(self, email, amount):
        self.credential_UpdateUserBalance(email, self.credential_GetUserBalance(email) - amount)


    def credential_helper_CalculateTimeDifferenceInHours(self, startTime, endTime):
        import datetime as dt
        start = dt.datetime.strptime(startTime, "%d/%m/%Y:%H/%M/%S")
        end = dt.datetime.strptime(endTime, "%d/%m/%Y:%H/%M/%S")
        timeDifference = end - start

        hours_passed = timeDifference.total_seconds() / 3600
        return hours_passed

    # Basic Utility Functions END !!! ---------------------------------------------------------------------------------------



    # Create Section !!! -----------------------------------------------------------------------------------------------------

    def credential_InsertNewUser(self, email, password):
        self.CredentialCollection.insert_one({
            "Email": email,
            "Password": password,
            "TotalEarnings": 0.0,
            "Balance": 0.0,
            "Withdrawals": []
        })

    def credential_InsertNewWithdrawal(self, email, date, time, amount, upiID):
        withdrawalObject = self.credential_CreateWithdrawalObject(date, time, amount, upiID)
        self.CredentialCollection.update_one({"Email": email}, {"$push": {"Withdrawals": withdrawalObject}})
        pass 

    # Create Section END !!! -------------------------------------------------------------------------------------------------




    # Read Section !!! -------------------------------------------------------------------------------------------------------

    def credential_GetUserInformation(self, email):
        return self.CredentialCollection.find_one({"Email": email})

    def credential_GetUserPassword(self, email):
        retrivedData = self.CredentialCollection.find_one({"Email": email})
        if retrivedData == None:
            return None

        return retrivedData['Password']

    def credential_GetUserBalance(self, email):
        retrivedData = self.CredentialCollection.find_one({"Email": email})
        if retrivedData == None:
            return None

        return retrivedData['Balance']

    def credential_GetUserTotalEarnings(self, email):
        retrivedData = self.CredentialCollection.find_one({"Email": email})
        if retrivedData == None:
            return None

        return retrivedData['TotalEarnings']

    def credential_GetUserWithdrawals(self, email):
        retrivedData = self.CredentialCollection.find_one({"Email": email})
        if retrivedData == None:
            return None

        return retrivedData['Withdrawals']

    # Read Section END !!! --------------------------------------------------------------------------------------------------


    # Update Section !!! -----------------------------------------------------------------------------------------------------

    def credential_UpdateUserInformation(self, email, password=None, newBalance=None, newTotalEarnings=None, newWithdrawals=None):
        pass

    def credential_UpdateUserPassword(self, email, newPassword):
        self.CredentialCollection.update_one({"Email": email}, {"$set": {"Password": newPassword}})

    def credential_UpdateUserBalance(self, email, newBalance):
        self.CredentialCollection.update_one({"Email": email}, {"$set": {"Balance": newBalance}})

    def credential_UpdateUserTotalEarnings(self, email, newTotalEarnings):
        self.CredentialCollection.update_one({"Email": email}, {"$set": {"TotalEarnings": newTotalEarnings}})
                        
    # Update Section END !!! -------------------------------------------------------------------------------------------------





    # Delete Section !!! -----------------------------------------------------------------------------------------------------

    # Delete Section END !!! -------------------------------------------------------------------------------------------------




    # Credential Collection Section END !!! ------------------------------------------------------------------------------------------------------------------------------





















    # UUID_Email_Mapping Collection Section !!! ------------------------------------------------------------------------------------------------------------------------------



    # Basic Utility Functions !!! -------------------------------------------------------------------------------------------

    def UEM_UuidEmail_CheckAndInsert(self, UUID, email):
        
        if self.UEM_CheckUuidExist(UUID) == False:
            self. UEM_InsertNewUUID(UUID)
            self.UEM_InsertNewEmail(UUID, email)
        
        if email not in self.UEM_GetUuidInfo(UUID)['Emails']:
            print("new Email UUID Pair Found")
            self.UEM_InsertNewEmail(UUID, email)

        return

    def UEM_CheckUuidExist(self, UUID):
        retrivedData = self.UEM_Collections.find_one({"UUID": UUID})
        if retrivedData == None:
            return False
        
        return True

    def UEM_UuidGPU_CheckAndInsert(self, UUID, GPU):
        if self.UEM_CheckUuidExist(UUID) == False:
            self. UEM_InsertNewUUID(UUID)
            self.UEM_InsertNewGPU(UUID, GPU)
        
        # print(self.UEM_GetUuidInfo(UUID))
        # print(type(self.UEM_GetUuidInfo(UUID)))
        if 'GPUs' not in self.UEM_GetUuidInfo(UUID):
            self.UEM_InsertNewGPU(UUID, GPU)
            return
        elif GPU not in self.UEM_GetUuidInfo(UUID)['GPUs']:
            self.UEM_InsertNewGPU(UUID, GPU)

        return

    # Basic Utility Functions END !!! ---------------------------------------------------------------------------------------





    # Create Section !!! -----------------------------------------------------------------------------------------------------

    def UEM_InsertNewUUID(self, UUID):
        self.UEM_Collections.insert_one({
            "UUID": UUID,
            "Emails": []
        })

    def UEM_InsertNewEmail(self, UUID, email):
        self.UEM_Collections.update_one({"UUID": UUID}, {"$push": {"Emails": email}})

    def UEM_InsertNewGPU(self, UUID, GPU):
        print("New Gpu Inserted Request")
        self.UEM_Collections.update_one({"UUID": UUID}, {"$push": {"GPUs": GPU}})


    # Create Section END !!! -------------------------------------------------------------------------------------------------




    # Read Section !!! -------------------------------------------------------------------------------------------------------

    def UEM_GetUuidInfo(self, UUID):
        return self.UEM_Collections.find_one({"UUID": UUID})

    # Read Section END !!! --------------------------------------------------------------------------------------------------



    # Update Section !!! -----------------------------------------------------------------------------------------------------
                
    # Update Section END !!! -------------------------------------------------------------------------------------------------


    # Delete Section !!! -----------------------------------------------------------------------------------------------------

    # Delete Section END !!! -------------------------------------------------------------------------------------------------





    # UUID_Email_Mapping Collection Section END !!! ------------------------------------------------------------------------------------------------------------------------------









    # User Activity Collection Section !!! ------------------------------------------------------------------------------------------------------------------------------




    # Basic Utility Functions !!! --------------------------------------------------------------------------------------------

    def activity_CreateAppSessionObject(self, UUID, startTime, endTime):
        return {"UUID": UUID, "StartTime": startTime, "EndTime": endTime}

    def activity_CreateContainerSessionObject(self, UUID, startTime, endTime):
        return {"UUID": UUID, "StartTime": startTime, "EndTime": endTime}

    # Basic Utility Functions END !!! ----------------------------------------------------------------------------------------




    # Create Section !!! -----------------------------------------------------------------------------------------------------

    def activity_CreateUserActivity(self, email):
        self.ActivityCollections.insert_one({
            "Email": email,
            "AppSessions": [],
            "ContainerSessions": []
        })

    def activity_InsertAppSession(self, email, UUID, startTime, endTime):
        appSessionObject = self.activity_CreateAppSessionObject(UUID, startTime, endTime)
        self.ActivityCollections.update_one({"Email": email}, {"$push": {"AppSessions": appSessionObject}})

    def activity_InsertContainerSession(self, email, UUID, startTime, endTime):
        containerSessionObject = self.activity_CreateContainerSessionObject(UUID, startTime, endTime)
        self.ActivityCollections.update_one({"Email": email}, {"$push": {"ContainerSessions": containerSessionObject}})

    # Create Section END !!! -------------------------------------------------------------------------------------------------




    # Read Section !!! -------------------------------------------------------------------------------------------------------

    def activity_GetUserActivity(self, email):
        return self.ActivityCollections.find_one({"Email": email})

    def activity_GetUserAppSessions(self, email):
        retrivedData = self.ActivityCollections.find_one({"Email": email})
        if retrivedData == None:
            return None

        return retrivedData['AppSessions']

    def activity_GetUserContainerSessions(self, email):
        retrivedData = self.ActivityCollections.find_one({"Email": email})
        if retrivedData == None:
            return None

        return retrivedData['ContainerSessions']

    # Read Section END !!! ---------------------------------------------------------------------------------------------------



    # Update Section !!! ------------------------------------------------------------------------------------------------------
                
    # Update Section END !!! -------------------------------------------------------------------------------------------------


    # Delete Section !!! -----------------------------------------------------------------------------------------------------

    # Delete Section END !!! -------------------------------------------------------------------------------------------------





    # User Activity Collection Section END !!! ------------------------------------------------------------------------------------------------------------------------------









    # Payments Collection Section !!! ------------------------------------------------------------------------------------------------------------------------------

    # Basic Utility Functions !!! --------------------------------------------------------------------------------------------
    # Basic Utility Functions END !!! ----------------------------------------------------------------------------------------



    # Create Section !!! -----------------------------------------------------------------------------------------------------

    def payments_InsertNewPayment(self, upiID, Amount, email, date, additonNote=""):
        self.PaymentsCollections.insert_one({
            "UpiID": upiID,
            "Amount": Amount,
            "Email": email,
            "Date": date,
            "Additonal Note": additonNote,
            "Status": "PENDING"
        })

    # Create Section END !!! -------------------------------------------------------------------------------------------------


    # Read Section !!! -------------------------------------------------------------------------------------------------------
    # Read Section END !!! ---------------------------------------------------------------------------------------------------

    # Update Section !!! ------------------------------------------------------------------------------------------------------  
    # Update Section END !!! -------------------------------------------------------------------------------------------------


    # Delete Section !!! -----------------------------------------------------------------------------------------------------
    # Delete Section END !!! -------------------------------------------------------------------------------------------------


    # Payments Collection Section END !!! --------------------------------------------------------------------------------------------------------------------------



