import smartpy as sp

class USDOracle(sp.Contract):
    def __init__(self, admin):
        
        self.init(USDPrice = sp.nat(0), keysset = sp.set([admin]) , owner = admin,securities = admin)
    
    @sp.entry_point
    def feedData(self,params):
        sp.if (self.data.keysset.contains(sp.sender)):
            self.data.USDPrice = params.price 
    
    @sp.entry_point
    def changeSecurities(self,params):

        sp.set_type(params, sp.TRecord(address = sp.TAddress))
        
        sp.verify(sp.sender == self.data.owner)

        self.data.securities = params.address

    @sp.entry_point
    def addDataContributor(self,params):
        sp.if sp.sender == self.data.owner:
            self.data.keysset.add(params.contributor)
            
    @sp.entry_point
    def MintToken(self,params):

        sp.set_type(params, sp.TRecord(loan = sp.TNat))

        data = sp.record(price=self.data.USDPrice,loan = params.loan)
        
        contract = sp.contract(sp.TRecord( price = sp.TNat, loan = sp.TNat),sp.sender,entry_point = "OracleMint").open_some()
        
        sp.transfer(data,sp.mutez(0),contract)

    @sp.entry_point 
    def LiquidateToken(self,params):

        sp.set_type(params, sp.TRecord(address = sp.TAddress))

        data = sp.record(price=self.data.USDPrice,address = params.address)
        
        contract = sp.contract(sp.TRecord( price = sp.TNat, address = sp.TAddress),sp.sender,entry_point = "OracleLiquidate").open_some()
        
        sp.transfer(data,sp.mutez(0),contract)


    @sp.entry_point
    def CollateralWithdraw(self,params):

        sp.set_type(params, sp.TRecord(amount = sp.TNat))

        data = sp.record(price=self.data.USDPrice,amount = params.amount)
        
        contract = sp.contract(sp.TRecord( price = sp.TNat, amount = sp.TNat),sp.sender,entry_point = "OracleWithdrawCollateral").open_some()
        
        sp.transfer(data,sp.mutez(0),contract)

    @sp.entry_point
    def SecuritiesPurchase(self,params):

        sp.set_type(params, sp.TRecord(xtz = sp.TNat, token = sp.TNat, order = sp.TNat , duration = sp.TNat , spender = sp.TAddress))

        duration = sp.set([1,7,14])

        sp.verify(params.xtz * self.data.USDPrice * 1000 >= params.token * 150)

        sp.verify(params.order * self.data.USDPrice*1000000000 >= params.token * 150 )

        sp.verify(duration.contains(params.duration))

        c = sp.contract(sp.TRecord(price = sp.TNat, duration = sp.TNat, order = sp.TNat, owner = sp.TAddress, spender = sp.TAddress ), self.data.securities, entry_point = "OraclePurchaseSecurity").open_some()

        mydata = sp.record(price = self.data.USDPrice,duration = params.duration , order = params.order,  owner = sp.sender , spender = params.spender)

        sp.transfer(mydata, sp.mutez(0), c)

    @sp.entry_point
    def SecuritiesExercise(self,params):

        sp.set_type(params, sp.TRecord(owner = sp.TAddress))

        sp.verify(sp.sender == params.owner)
        
        c = sp.contract(sp.TRecord(price = sp.TNat, owner = sp.TAddress), self.data.securities, entry_point = "OracleExerciseSecurity").open_some()

        mydata = sp.record(price = self.data.USDPrice,owner = sp.sender)

        sp.transfer(mydata, sp.mutez(0), c)


class Securities(sp.Contract):

    def __init__(self,admin,token,oracle):

            self.init(
            Securities= sp.big_map(),LiquidityProvider = sp.big_map(),
            poolSet=sp.set(),
            totalSupply=sp.nat(0),
            adminAccount=sp.nat(0),
            PoolSize = sp.nat(10),
            InterestRate=sp.map(),
            administrator = admin,
            token=token,    
            oracle=oracle)



    @sp.entry_point
    def OraclePurchaseSecurity(self,params):
        
        sp.set_type(params, sp.TRecord(price = sp.TNat, duration = sp.TNat, order = sp.TNat, owner = sp.TAddress, spender = sp.TAddress ))

        sp.verify(sp.sender == self.data.oracle)
        sp.verify(~self.data.Securities.contains(params.owner))

        Deadline = sp.now.add_days(sp.to_int(params.duration))

        self.data.Securities[params.owner] = sp.record(strikePrice = params.price, pool = sp.map(),
        adminpayment = sp.nat(0), options = params.order, expiry = Deadline
        )

        TotalAmount = sp.local('TotalAmount',params.price*params.order*abs(10000000))
        CollateralValue = sp.local('CollateralValue',sp.nat(0))

        self.data.InterestRate[1] = sp.nat(1)
        self.data.InterestRate[7] = sp.nat(2)
        self.data.InterestRate[14] = sp.nat(4)
        

        PremiumTotal = sp.local('PremiumTotal',params.price*params.order*self.data.InterestRate[params.duration]*abs(100000))
        PremiumLiquidity = sp.local('PremiumLiquidity',sp.nat(0))

        del self.data.InterestRate[1]
        del self.data.InterestRate[7]
        del self.data.InterestRate[14]

        self.data.adminAccount += params.price*params.order*100000
    
        sp.verify(self.data.totalSupply >= TotalAmount.value)

        sp.for i in self.data.poolSet.elements():

            self.data.Securities[params.owner].pool[i] = (self.data.LiquidityProvider[i].amount*TotalAmount.value)/(self.data.totalSupply)
            
            self.data.LiquidityProvider[i].locked += (self.data.LiquidityProvider[i].amount*TotalAmount.value)/(self.data.totalSupply)

            CollateralValue.value += (self.data.LiquidityProvider[i].amount*TotalAmount.value)/(self.data.totalSupply)

            self.data.LiquidityProvider[i].premium += (self.data.LiquidityProvider[i].amount*PremiumTotal.value)/(self.data.totalSupply)
            PremiumLiquidity.value += (self.data.LiquidityProvider[i].amount*PremiumTotal.value)/(self.data.totalSupply)

            self.data.LiquidityProvider[i].amount = abs(self.data.LiquidityProvider[i].amount - (self.data.LiquidityProvider[i].amount*TotalAmount.value)/(self.data.totalSupply) )
        

        self.data.adminAccount += abs(PremiumTotal.value - PremiumLiquidity.value)

        sp.verify(params.price*params.order*100000 > abs(TotalAmount.value - CollateralValue.value))

        self.data.Securities[params.owner].adminpayment += abs(TotalAmount.value - CollateralValue.value)
        
        self.data.adminAccount = abs(self.data.adminAccount - abs(TotalAmount.value - CollateralValue.value))
        
        self.data.totalSupply = abs(self.data.totalSupply - CollateralValue.value)

        PremiumTotal.value += params.price*params.order*100000

        # Premium Transfer Call 

        c = sp.contract(sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress , value = sp.TNat), self.data.token, entry_point = "transfer").open_some()

        mydata = sp.record(from_ = params.spender ,to_ = sp.self_address, value = PremiumTotal.value)

        sp.transfer(mydata, sp.mutez(0), c)


    @sp.entry_point
    def OracleExerciseSecurity(self,params):
        
        sp.set_type(params, sp.TRecord(price = sp.TNat, owner = sp.TAddress))
        sp.verify(sp.sender == self.data.oracle)

        sp.verify(sp.now <= self.data.Securities[params.owner].expiry)

        sp.verify(self.data.Securities[params.owner].strikePrice > params.price)

        self.data.adminAccount += self.data.Securities[params.owner].adminpayment

        Amount = sp.local('Amount',abs(self.data.Securities[params.owner].strikePrice - params.price)*10000000)
        Amount.value = Amount.value*self.data.Securities[params.owner].options

        CalAmount = sp.local('CalAmount',sp.nat(0))

        PoolAmount = sp.local('PoolAmount',self.data.Securities[params.owner].strikePrice*self.data.Securities[params.owner].options*10000000)
        PoolAmount.value = abs(PoolAmount.value - self.data.Securities[params.owner].adminpayment)
        
        sp.for i in self.data.Securities[params.owner].pool.keys():
        
            CalAmount.value += (self.data.Securities[params.owner].pool[i]*Amount.value)/(PoolAmount.value)

            self.data.LiquidityProvider[i].locked = abs(self.data.LiquidityProvider[i].locked - self.data.Securities[params.owner].pool[i])

            self.data.Securities[params.owner].pool[i] = abs(self.data.Securities[params.owner].pool[i] - (self.data.Securities[params.owner].pool[i]*Amount.value)/(PoolAmount.value) )
            
            sp.if self.data.poolSet.contains(i):
                self.data.LiquidityProvider[i].amount += self.data.Securities[params.owner].pool[i]
                self.data.totalSupply += self.data.Securities[params.owner].pool[i]
            sp.else:
                self.data.LiquidityProvider[i].premium += self.data.Securities[params.owner].pool[i]

           
        sp.if Amount.value != CalAmount.value:
            sp.verify(self.data.adminAccount > abs(Amount.value - CalAmount.value))
            self.data.adminAccount = abs(self.data.adminAccount - abs(Amount.value - CalAmount.value))

        c = sp.contract(sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress , value = sp.TNat), self.data.token, entry_point = "transfer").open_some()

        mydata = sp.record(from_ = sp.self_address,to_ = params.owner, value = Amount.value)

        sp.transfer(mydata, sp.mutez(0), c)

        del self.data.Securities[params.owner]
    
    @sp.entry_point
    def FreeSecurity(self,params):

        sp.set_type(params, sp.TRecord(address = sp.TAddress))

        sp.verify(self.data.Securities.contains(params.address))

        sp.if sp.now > self.data.Securities[params.address].expiry :
        
            sp.for i in self.data.Securities[params.address].pool.keys():

                sp.if self.data.poolSet.contains(i):

                    self.data.LiquidityProvider[i].amount += self.data.Securities[params.address].pool[i]
                    self.data.totalSupply += self.data.Securities[params.address].pool[i]
                
                sp.else:
                    self.data.LiquidityProvider[i].premium += self.data.Securities[params.address].pool[i]

                self.data.LiquidityProvider[i].locked = abs(self.data.LiquidityProvider[i].locked - self.data.Securities[params.address].pool[i])

            self.data.adminAccount += self.data.Securities[params.address].adminpayment

            del self.data.Securities[params.address]

    @sp.entry_point 
    def ContractWriter(self,params):

        sp.set_type(params, sp.TRecord(amount = sp.TNat))

        sp.verify(params.amount >= 1000000000)
        sp.verify(params.amount % 1000000000 == 0 )

        sp.verify(sp.len(self.data.poolSet.elements()) <= self.data.PoolSize)

        sp.if self.data.poolSet.contains(sp.sender):

            self.data.LiquidityProvider[sp.sender].amount += params.amount 

        sp.else:  

            sp.if self.data.LiquidityProvider.contains(sp.sender):
                self.data.LiquidityProvider[sp.sender].amount += params.amount 

            sp.else:
                self.data.LiquidityProvider[sp.sender] = sp.record(amount=0,premium=sp.nat(0),locked = sp.nat(0))        
                self.data.LiquidityProvider[sp.sender].amount += params.amount 

            self.data.poolSet.add(sp.sender)

        self.data.totalSupply += params.amount 

        # Transfer function 

        c = sp.contract(sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress , value = sp.TNat), self.data.token, entry_point = "transfer").open_some()

        mydata = sp.record(from_ = sp.sender,to_ = sp.self_address, value = params.amount)

        sp.transfer(mydata, sp.mutez(0), c)


    @sp.entry_point
    def WithdrawToken(self,params):
        sp.verify(self.data.LiquidityProvider.contains(sp.sender))

        c = sp.contract(sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress , value = sp.TNat), self.data.token, entry_point = "transfer").open_some()

        mydata = sp.record(from_ = sp.self_address,to_ = sp.sender, value = self.data.LiquidityProvider[sp.sender].premium)

        sp.transfer(mydata, sp.mutez(0), c)

        self.data.LiquidityProvider[sp.sender].premium = 0 

    @sp.entry_point 
    def ExitContractWriter(self,params):
        
        sp.verify(self.data.poolSet.contains(sp.sender))
        
        self.data.poolSet.remove(sp.sender)

        # Reduce Total Supply
        self.data.totalSupply = abs(self.data.totalSupply-self.data.LiquidityProvider[sp.sender].amount)

        c = sp.contract(sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress , value = sp.TNat), self.data.token, entry_point = "transfer").open_some()

        mydata = sp.record(from_ = sp.self_address,to_ = sp.sender, value = self.data.LiquidityProvider[sp.sender].premium + self.data.LiquidityProvider[sp.sender].amount)

        sp.transfer(mydata, sp.mutez(0), c)


        self.data.LiquidityProvider[sp.sender].premium = 0 
        self.data.LiquidityProvider[sp.sender].amount = 0 

    @sp.entry_point
    def ChangePoolSize(self,params):

        sp.verify(sp.sender == self.data.administrator)

        sp.set_type(params, sp.TRecord(size = sp.TNat))

        self.data.PoolSize = params.size


    @sp.entry_point
    def AdminWithdraw(self,params):
        
        sp.verify(sp.sender == self.data.administrator)

        sp.verify(self.data.adminAccount > 0  )

        c = sp.contract(sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress , value = sp.TNat), self.data.token, entry_point = "transfer").open_some()

        mydata = sp.record(from_ = sp.self_address,to_ = sp.sender, value = self.data.adminAccount)

        sp.transfer(mydata, sp.mutez(0), c)

        self.data.adminAccount = 0 

if "templates" not in __name__:
    @sp.add_test(name = "Securities Contract")
    def test():

        scenario = sp.test_scenario()

        # sp.test_account generates ED25519 key-pairs deterministically:
        admin = sp.test_account("Admin")
        
        alice = sp.test_account("Alice")
        bob   = sp.test_account("Bob")
        robert = sp.test_account("Robert")

        scenario.h1("Contract")

        oracle  = USDOracle(admin.address)
        scenario += oracle 
  
        options = Securities(sp.address("tz1XfbFQgxj1sSfe2YyJPba5ZQuKMcV4FXAX"),sp.address("KT1HsVdNMvy4uTeorCFJD2kPVGzHXhpzJZjV"),oracle.address)
        scenario += options
        
        scenario += oracle.feedData(price=230).run(sender=admin)

        scenario += options.ContractWriter(amount=1000000000).run(sender=alice)
        scenario += options.ContractWriter(amount=2000000000).run(sender=robert)

        scenario += oracle.changeSecurities(address=options.address).run(sender=admin)
        scenario += oracle.SecuritiesPurchase(xtz = 1000000, token = 1000000000 , duration = 1 , spender = bob.address, order = 1).run(sender = bob)
        scenario += oracle.feedData(price=200).run(sender=admin)

        scenario += oracle.SecuritiesExercise(owner = bob.address).run(sender = bob )