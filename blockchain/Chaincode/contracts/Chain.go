package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

type SmartContract struct {
	contractapi.Contract
}

type ParkingSlot struct {
	ID        string `json:"id"`
	Location  string `json:"location"`
	Occupied  bool   `json:"occupied"`
	Timestamp string `json:"timestamp"`
}

func (s *SmartContracts) UpdateStatus(ctx contractapi.TransactionContextInterface, id string, occupied bool, location string) error {
	slot := ParkingSlot{
		ID:        id,
		Location:  location, 
		Occupied:  occupied,
		Timestamp: time.Now().Format(time.RFC3339),
	}
	slotJSON, _ := json.Marshal(slot)
	return ctx.GetStub().PutState(id, slotJSON)
}

func (s *SmartContract) GetAllSlots(ctx contractapi.TransactionContextInterface) ([]ParkingSlot, error) {
	resultsIterator, _ := ctx.GetStub().GetStateByRange("", "")
	defer resultsIterator.Close()

	var slots []ParkingSlot
	for resultsIterator.HasNext() {
		queryResponse, _ := resultsIterator.Next()
		var slot ParkingSlot
		json.Unmarshal(queryResponse.Value, &slot)
		slots = append(slots, slot)
	}
	return slots, nil
}

func main() {
	chaincode, err := contractapi.NewChaincode(new(SmartContract))
	if err != nil {
		fmt.Printf("Error create parking chaincode: %s", err.Error())
		return
	}
	if err := chaincode.Start(); err != nil {
		fmt.Printf("Error starting parking chaincode: %s", err.Error())
	}
}
