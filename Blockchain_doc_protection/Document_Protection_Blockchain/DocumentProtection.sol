pragma solidity >=0.8.11 <=0.8.19;

contract DocumentProtection {
    
    struct Evidence {
        string ipfsHash;
        string fileName;
        string fileHash;
        uint256 timestamp;
        address uploader;
        string description;
        string tags;
        bool isActive;
    }
    
    struct AccessLog {
        address user;
        uint256 timestamp;
        string action;
        string evidenceId;
    }
    
    struct User {
        address userAddress;
        string role; // "admin", "investigator", "viewer"
        bool isAuthorized;
        uint256 registrationTime;
    }
    
    mapping(string => Evidence) public evidences;
    mapping(address => User) public users;
    mapping(string => AccessLog[]) public auditTrail;
    mapping(address => bool) public authorizedUsers;
    
    string[] public evidenceIds;
    address public admin;
    
    event EvidenceUploaded(string indexed evidenceId, string ipfsHash, address uploader);
    event EvidenceAccessed(string indexed evidenceId, address accessor, string action);
    event UserAuthorized(address indexed user, string role);
    event UserRevoked(address indexed user);
    
    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin can perform this action");
        _;
    }
    
    modifier onlyAuthorized() {
        require(authorizedUsers[msg.sender] || msg.sender == admin, "Not authorized");
        _;
    }
    
    constructor() {
        admin = msg.sender;
        users[admin] = User(admin, "admin", true, block.timestamp);
        authorizedUsers[admin] = true;
    }
    
    function uploadEvidence(
        string memory _evidenceId,
        string memory _ipfsHash,
        string memory _fileName,
        string memory _fileHash,
        string memory _description,
        string memory _tags
    ) public onlyAuthorized {
        require(bytes(evidences[_evidenceId].ipfsHash).length == 0, "Evidence ID already exists");
        
        evidences[_evidenceId] = Evidence({
            ipfsHash: _ipfsHash,
            fileName: _fileName,
            fileHash: _fileHash,
            timestamp: block.timestamp,
            uploader: msg.sender,
            description: _description,
            tags: _tags,
            isActive: true
        });
        
        evidenceIds.push(_evidenceId);
        
        // Log the upload action
        auditTrail[_evidenceId].push(AccessLog({
            user: msg.sender,
            timestamp: block.timestamp,
            action: "UPLOAD",
            evidenceId: _evidenceId
        }));
        
        emit EvidenceUploaded(_evidenceId, _ipfsHash, msg.sender);
    }
    
    function getEvidence(string memory _evidenceId) 
        public 
        onlyAuthorized 
        returns (Evidence memory) 
    {
        require(evidences[_evidenceId].isActive, "Evidence not found or inactive");
        
        // Log the access
        auditTrail[_evidenceId].push(AccessLog({
            user: msg.sender,
            timestamp: block.timestamp,
            action: "VIEW",
            evidenceId: _evidenceId
        }));
        
        emit EvidenceAccessed(_evidenceId, msg.sender, "VIEW");
        
        return evidences[_evidenceId];
    }
    
    function verifyEvidence(string memory _evidenceId, string memory _fileHash) 
        public 
        view 
        returns (bool) 
    {
        return keccak256(abi.encodePacked(evidences[_evidenceId].fileHash)) == 
               keccak256(abi.encodePacked(_fileHash));
    }
    
    function authorizeUser(address _user, string memory _role) public onlyAdmin {
        users[_user] = User(_user, _role, true, block.timestamp);
        authorizedUsers[_user] = true;
        emit UserAuthorized(_user, _role);
    }
    
    function revokeUser(address _user) public onlyAdmin {
        users[_user].isAuthorized = false;
        authorizedUsers[_user] = false;
        emit UserRevoked(_user);
    }
    
    function getAuditTrail(string memory _evidenceId) 
        public 
        view 
        onlyAuthorized 
        returns (AccessLog[] memory) 
    {
        return auditTrail[_evidenceId];
    }
    
    function getAllEvidenceIds() public view onlyAuthorized returns (string[] memory) {
        return evidenceIds;
    }
    
    function getUserRole(address _user) public view returns (string memory) {
        return users[_user].role;
    }
    
    function isUserAuthorized(address _user) public view returns (bool) {
        return authorizedUsers[_user];
    }
}
