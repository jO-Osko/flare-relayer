# Relayer Project Instructions
This project is a blockchain relayer between Coston and Sepolia networks.
The addresses of the relayer contracts are the following:
```
COSTON_RELAY=0x2f48135AdF44c99999cA0d6d21bD49466AaD74Fd
SEPOLIA_RELAY=0x7b4d5e9388dBdB0161186D605379dafA3dc22100
```
## About
Flare relayer is a connection between Ethereum(sepolia) & Flare(coston) blockchain that allows the transfer calldata data and/or tokens from one chain to another.

## Instructions
This is done by calling the **requestRelay** function on the relayer contract of the first network. The function needs to be called with the following arguments:

- **_relayTarget** is the address of the contract, that we want to interact with. This target contract is on the second network and will receive the amount of tokens that are sent to the relayer on the first network.
- **_additionalCalldata** are the keccak encoded bytes that contain the function name and the arguments of the function we want to call on the target contract.
- **_sourceToken** is the address of the token that we send to the relayer contract on the first network. The relayer contract will calculate the token pair (which is on the second network) of this token, that will be sent to the target network.
- **_amount** is an amount of source tokens we send. The same amount will be received by the relay target contract on the second network.

When this call to the relayer contract on the first network is made, the contract calculates the token pair of the source token. If the source token is not supported, the function throws an exception and reverts the transaction. The contract then transfers the specified amount of source tokens from the transaction sender to the owner of the relayer contract. Finally the contract emits a **RelayRequested** event.

This event is then caught by us (the relayer) and we call the **executeRelay** function on the relayer contract of the second network with correct arguments. 

The results of this call are:
- The *relay target* contract (on the second network) receives *amount* of tokens, that are the token pair of the *source token (on the first network)*.  
- The function on the *relay target* that was encoded inside *additional calldata* is also executed.


## Example of the good call
An example script with a good call is in the *```relay/management/commands/request_with_data.py```* file.





