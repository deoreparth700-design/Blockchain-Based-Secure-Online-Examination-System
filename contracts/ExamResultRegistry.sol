// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract ExamResultRegistry {
    address public owner;

    struct ResultRecord {
        bytes32 resultHash;
        address recordedBy;
        uint256 timestamp;
    }

    // Mapping from attempt ID to ResultRecord
    mapping(uint256 => ResultRecord) public records;

    event ResultRecorded(
        uint256 indexed attemptId,
        bytes32 resultHash,
        address indexed recordedBy,
        uint256 timestamp
    );

    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Only the authorized teacher can perform this action");
        _;
    }

    function recordResult(uint256 attemptId, bytes32 resultHash) public onlyOwner {
        require(records[attemptId].timestamp == 0, "Result already recorded for this attempt");

        records[attemptId] = ResultRecord({
            resultHash: resultHash,
            recordedBy: msg.sender,
            timestamp: block.timestamp
        });

        emit ResultRecorded(attemptId, resultHash, msg.sender, block.timestamp);
    }

    function verifyResult(uint256 attemptId, bytes32 resultHash) public view returns (bool) {
        return (records[attemptId].timestamp != 0 && records[attemptId].resultHash == resultHash);
    }
}
