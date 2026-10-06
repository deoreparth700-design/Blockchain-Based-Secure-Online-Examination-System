// Ensure ethers is loaded
if (typeof ethers === 'undefined') {
    console.error("Ethers.js is not loaded.");
}

async function connectMetaMask() {
    if (!window.ethereum) {
        alert("MetaMask not installed. Please install MetaMask to use this feature.");
        return null;
    }

    try {
        const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
        const walletAddress = accounts[0];
        
        // Check Network
        const chainId = await window.ethereum.request({ method: 'eth_chainId' });
        if (chainId !== ETHEREUM_CONFIG.SEPOLIA_CHAIN_ID) {
            try {
                await window.ethereum.request({
                    method: 'wallet_switchEthereumChain',
                    params: [{ chainId: ETHEREUM_CONFIG.SEPOLIA_CHAIN_ID }],
                });
            } catch (switchError) {
                if (switchError.code === 4902) {
                    alert("Please add the Sepolia test network to MetaMask.");
                } else {
                    alert("Please switch to the Sepolia network.");
                }
                return null;
            }
        }
        
        return walletAddress;
    } catch (error) {
        console.error("User rejected request or error occurred", error);
        return null;
    }
}

async function anchorResultOnEthereum(attemptId, resultHashBase) {
    if (ETHEREUM_CONFIG.CONTRACT_ADDRESS === "YOUR_DEPLOYED_CONTRACT_ADDRESS") {
        alert("Please configure the smart contract address in static/js/ethereum-config.js first.");
        return;
    }

    const walletAddress = await connectMetaMask();
    if (!walletAddress) return;

    try {
        updateStatus("Waiting for MetaMask approval...", "pending");
        
        const provider = new ethers.providers.Web3Provider(window.ethereum);
        const signer = provider.getSigner();
        const contract = new ethers.Contract(ETHEREUM_CONFIG.CONTRACT_ADDRESS, ETHEREUM_CONFIG.CONTRACT_ABI, signer);
        
        // Ensure resultHash is 32 bytes (64 hex characters + '0x')
        const bytes32Hash = "0x" + resultHashBase;
        
        const tx = await contract.recordResult(attemptId, bytes32Hash);
        
        updateStatus("Transaction submitted... Waiting for confirmation.", "pending");
        
        const receipt = await tx.wait();
        
        // Save to backend
        await fetch(`/api/anchor_result/${attemptId}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                tx_hash: receipt.transactionHash,
                contract_address: ETHEREUM_CONFIG.CONTRACT_ADDRESS,
                result_hash: bytes32Hash,
                wallet_address: walletAddress
            })
        });

        updateStatus("Ethereum anchor successful.", "success");
        setTimeout(() => location.reload(), 1500);
        
    } catch (error) {
        console.error("Anchoring failed", error);
        if (error.code === 4001) {
            updateStatus("Transaction rejected by user.", "error");
        } else {
            updateStatus("Transaction failed. Are you the contract owner?", "error");
        }
    }
}

async function verifyEthereumResult(attemptId, resultHashBase) {
    if (ETHEREUM_CONFIG.CONTRACT_ADDRESS === "YOUR_DEPLOYED_CONTRACT_ADDRESS") {
        alert("Please configure the smart contract address in static/js/ethereum-config.js first.");
        return;
    }

    try {
        updateStatus("Verifying with Ethereum...", "pending");
        
        const provider = new ethers.providers.Web3Provider(window.ethereum || ethers.getDefaultProvider("sepolia"));
        const contract = new ethers.Contract(ETHEREUM_CONFIG.CONTRACT_ADDRESS, ETHEREUM_CONFIG.CONTRACT_ABI, provider);
        
        const bytes32Hash = "0x" + resultHashBase;
        const isValid = await contract.verifyResult(attemptId, bytes32Hash);
        
        if (isValid) {
            updateStatus("Ethereum verification successful. Result hash matches.", "success");
        } else {
            updateStatus("Ethereum verification failed. Hash does not match or is not anchored.", "error");
        }
    } catch (error) {
        console.error("Verification error", error);
        updateStatus("Error verifying on Ethereum.", "error");
    }
}

function updateStatus(message, type) {
    const el = document.getElementById("eth-status");
    if (el) {
        el.innerText = message;
        el.className = `eth-status eth-${type}`;
    } else {
        alert(message);
    }
}
