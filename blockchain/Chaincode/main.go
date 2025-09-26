package main

import (
	"log"

	"kbaauto/contracts"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

func main() {
	carContract := new(contracts.SmartContract)

	chaincode, err := contractapi.NewChaincode(carContract)

	if err != nil {
		log.Panicf("Could not create chaincode : %v", err)
	}

	err = chaincode.Start()

	if err != nil {
		log.Panicf("Failed to start chaincode : %v", err)
	}
}
