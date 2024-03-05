# Relayer project

The projects consists of a blockchain relayer between Coston and Sepolia networks. 

The addresses of the relayer contracts are the following:
```
COSTON_RELAY=0x2f48135AdF44c99999cA0d6d21bD49466AaD74Fd
SEPOLIA_RELAY=0x7b4d5e9388dBdB0161186D605379dafA3dc22100
```

## What happens
To enact the relayer call from one network to another, the **requestRelay** function is called on the relayer contract on the first network (*relay/management/commands/request_with_data.py*). This will emit a **RelayRequested** event, that is detected by the main script (*relay/management/commands/start_relay.py*). With the information collected from the logs of the emitted event, the **executeRelay** function is then called on the relayer contract on the second network. This function also executes a call that is written inside the **additionalCalldata** field of the initial event, if there is one. The relayer call is also saved as a Django database object.


## How to run it
First start the listener for the network that we want to listen to with a script in the *start_relay.py* file (e.g. "coston"):
```
afh manage start_relay coston
```

Then run the script in the *request_with_data.py* file, to enact the relayer call. This should be done on the same network that we're listening to.
```
afh manage request_with_data coston
```

## Example of the transactions that are made (start network is coston)
Relayer call (Request Relay method) transaction hash:
```
tx_hash = 0x3cf4d2b401024d1d6c26908aa67f3622ab5cc2d0dbc36c84c4c7a7b93d4d0612
```
This transaction is made from *us* to the *COSTON_RELAY* contract.

We then make the transaction (Execute Relay mothed) on the *SEPOLIA_RELAY* contract. The transaction has is:
```
# sepolia address
tx_hash = 0xde40ff2e5d926903a9569fc94f00d49b4d889bbd3971628929ea44d1ae94d206
```

Both of these transaction include some token transfers, so that all the contracts have enough tokens that they can execute their calls. The Execute Relay methos transaction also enacts the call that is encoded in the *additionalCalldata* argument of the method. This function is called on the contract with the *relayTarget* address (another argument of the method).
