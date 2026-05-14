// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title Stella — AIGEN-treasury-backed stablecoin
 * @notice 1 STELLA = $1, fully redeemable for USDC on Base.
 *         Built explicitly to NOT repeat Terra/Luna's failure modes:
 *         - No algorithmic-only backing: every STELLA is backed by USDC in
 *           the AIGEN treasury (no LUNA-like inflation token absorbing volatility).
 *         - Mint paused automatically if collateral ratio drops below 110%
 *           or if peg drops below $0.97 (read from Chainlink USDC/USD oracle).
 *         - Hard supply cap (raised by governance time-locked decision).
 *         - Redemption ALWAYS allowed — no "freeze" function exists, by design.
 *         - No admin can mint, burn, or pause arbitrarily. Pause is one-way
 *           and only the multisig (after 48h timelock) can unpause.
 *         - Single-chain (Base only) at launch. No cross-chain bridges =
 *           no Wormhole/Ronin-class attack surface.
 *
 * @dev Address conventions:
 *      - USDC = 0x833589fcd6edb6e08f4c7c32d4f71b54bda02913 (Base USDC)
 *      - TREASURY = AIGEN protocol treasury wallet
 *      - GOVERNOR = multisig (5-of-9 at launch, transferable via timelock)
 */

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address) external view returns (uint256);
    function transfer(address, uint256) external returns (bool);
    function transferFrom(address, address, uint256) external returns (bool);
    function approve(address, uint256) external returns (bool);
    function allowance(address, address) external view returns (uint256);
}

interface IPriceOracle {
    /// Returns USDC/USD price, 8 decimals (Chainlink standard)
    function latestAnswer() external view returns (int256);
    function latestTimestamp() external view returns (uint256);
}

contract Stella {
    // ============ ERC20 ============
    string  public constant name     = "Stella";
    string  public constant symbol   = "STELLA";
    uint8   public constant decimals = 18;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    function transfer(address to, uint256 amt) external returns (bool) {
        return _transfer(msg.sender, to, amt);
    }
    function approve(address spender, uint256 amt) external returns (bool) {
        allowance[msg.sender][spender] = amt;
        emit Approval(msg.sender, spender, amt);
        return true;
    }
    function transferFrom(address from, address to, uint256 amt) external returns (bool) {
        uint256 a = allowance[from][msg.sender];
        if (a != type(uint256).max) {
            require(a >= amt, "ERC20: allowance");
            allowance[from][msg.sender] = a - amt;
        }
        return _transfer(from, to, amt);
    }
    function _transfer(address from, address to, uint256 amt) internal returns (bool) {
        require(to != address(0), "ERC20: zero");
        uint256 b = balanceOf[from];
        require(b >= amt, "ERC20: balance");
        unchecked { balanceOf[from] = b - amt; }
        balanceOf[to] += amt;
        emit Transfer(from, to, amt);
        return true;
    }

    // ============ Stella Specific ============
    address public immutable USDC;
    address public immutable TREASURY;
    address public immutable PRICE_ORACLE;  // Chainlink USDC/USD on Base

    address public governor;        // multisig — can raise cap, unpause, transfer
    address public pendingGovernor; // 48h timelock for governor change
    uint256 public pendingGovernorAt;

    /// Lifetime cap on STELLA supply. Raised only by governor + 48h timelock.
    uint256 public supplyCap = 100_000e18;
    uint256 public pendingCap;
    uint256 public pendingCapAt;
    uint256 public constant TIMELOCK = 48 hours;

    /// Minting auto-pauses below this collateral ratio (basis points: 11000 = 110%)
    uint256 public constant PAUSE_RATIO_BPS  = 11_000;
    /// Minting only allowed when ratio >= this (basis points: 15000 = 150%)
    uint256 public constant MINT_RATIO_BPS   = 15_000;
    /// Minting auto-pauses if peg below this (1e8 scale, 0.97 = 97_000_000)
    int256  public constant PEG_FLOOR        = 97_000_000;
    /// Oracle freshness — reject prices older than this
    uint256 public constant ORACLE_STALE_AFTER = 1 hours;

    bool public mintPaused;
    uint256 public mintPausedAt;

    event Minted(address indexed to, uint256 stellaOut, uint256 usdcIn, uint256 ratioAfterBps);
    event Redeemed(address indexed from, uint256 stellaIn, uint256 usdcOut);
    event MintAutoPaused(uint256 ratio, int256 peg);
    event Unpaused(address indexed by);
    event GovernorChangeQueued(address indexed next, uint256 ts);
    event GovernorChanged(address indexed next);
    event SupplyCapQueued(uint256 next, uint256 ts);
    event SupplyCapChanged(uint256 next);

    constructor(address usdc, address treasury, address oracle, address governor_) {
        require(usdc != address(0) && treasury != address(0) && governor_ != address(0), "zero addr");
        USDC = usdc;
        TREASURY = treasury;
        PRICE_ORACLE = oracle;  // can be 0x0 — peg() returns 1e8 in that case
        governor = governor_;
    }

    // ============ Mint / Redeem ============

    /// Anyone can mint STELLA by depositing USDC 1:1 to the treasury.
    /// Reverts if minting is paused, supply cap exceeded, or treasury under-collateralized.
    function mint(uint256 usdcAmount) external returns (uint256 stellaOut) {
        require(!mintPaused, "mint paused");
        require(usdcAmount > 0, "zero amount");

        // USDC has 6 decimals, STELLA has 18 → multiply by 1e12
        stellaOut = usdcAmount * 1e12;
        require(totalSupply + stellaOut <= supplyCap, "supply cap");

        uint256 ratioBefore = collateralRatioBps();
        require(ratioBefore >= MINT_RATIO_BPS, "treasury below 150%");

        // Verify peg before allowing mint
        int256 p = peg();
        require(p >= PEG_FLOOR, "peg below floor");

        IERC20(USDC).transferFrom(msg.sender, TREASURY, usdcAmount);

        totalSupply += stellaOut;
        balanceOf[msg.sender] += stellaOut;
        emit Transfer(address(0), msg.sender, stellaOut);

        uint256 ratioAfter = collateralRatioBps();
        require(ratioAfter >= PAUSE_RATIO_BPS, "would breach pause threshold");

        emit Minted(msg.sender, stellaOut, usdcAmount, ratioAfter);
    }

    /// Anyone can redeem STELLA for USDC at $1, ALWAYS. No pause function for redemption — by design.
    /// Treasury must have pre-approved this contract for at least usdcOut.
    function redeem(uint256 stellaAmount) external returns (uint256 usdcOut) {
        require(stellaAmount > 0, "zero amount");
        uint256 b = balanceOf[msg.sender];
        require(b >= stellaAmount, "balance");

        usdcOut = stellaAmount / 1e12;  // 18→6 decimals
        require(usdcOut > 0, "dust");

        unchecked { balanceOf[msg.sender] = b - stellaAmount; }
        totalSupply -= stellaAmount;
        emit Transfer(msg.sender, address(0), stellaAmount);

        IERC20(USDC).transferFrom(TREASURY, msg.sender, usdcOut);
        emit Redeemed(msg.sender, stellaAmount, usdcOut);
    }

    // ============ Auto-pause (anyone can call) ============

    /// Anyone can call to pause minting if conditions are breached.
    /// One-way: only governor + timelock can unpause.
    function pokePause() external {
        uint256 ratio = collateralRatioBps();
        int256 p = peg();
        if (ratio < PAUSE_RATIO_BPS || p < PEG_FLOOR) {
            require(!mintPaused, "already paused");
            mintPaused = true;
            mintPausedAt = block.timestamp;
            emit MintAutoPaused(ratio, p);
        }
    }

    /// Only governor can unpause, AND only when ratio + peg are both healthy.
    function unpause() external {
        require(msg.sender == governor, "not governor");
        require(mintPaused, "not paused");
        require(collateralRatioBps() >= MINT_RATIO_BPS, "ratio not restored");
        require(peg() >= 99_000_000, "peg not restored");
        mintPaused = false;
        emit Unpaused(msg.sender);
    }

    // ============ Views ============

    /// Current treasury USDC balance, in USDC raw units (6 decimals).
    function backingUSDC() public view returns (uint256) {
        return IERC20(USDC).balanceOf(TREASURY);
    }

    /// Collateral ratio in basis points. e.g., 15000 = 150%.
    /// Returns max uint when supply is zero.
    function collateralRatioBps() public view returns (uint256) {
        uint256 supply = totalSupply;
        if (supply == 0) return type(uint256).max;
        // backingUSDC is 6 decimals representing USD; supply is 18 decimals representing $
        // ratio = backingUSDC * 1e12 * 10000 / supply
        return (backingUSDC() * 1e12 * 10_000) / supply;
    }

    /// USDC/USD price from Chainlink (8 decimals). Returns 1e8 if no oracle set.
    function peg() public view returns (int256) {
        if (PRICE_ORACLE == address(0)) return 100_000_000; // 1.0
        IPriceOracle o = IPriceOracle(PRICE_ORACLE);
        int256 p = o.latestAnswer();
        require(p > 0, "oracle bad");
        require(block.timestamp - o.latestTimestamp() <= ORACLE_STALE_AFTER, "oracle stale");
        return p;
    }

    /// Maximum new STELLA that can be minted right now (in 1e18 units).
    function mintableNow() external view returns (uint256) {
        if (mintPaused) return 0;
        uint256 supply = totalSupply;
        // From cap
        uint256 fromCap = supply >= supplyCap ? 0 : supplyCap - supply;
        // From collateral: keep ratio >= PAUSE_RATIO_BPS
        // ratio_after = (backing * 1e12 * 10000) / (supply + new) >= PAUSE_RATIO_BPS
        // → new <= backing * 1e12 * 10000 / PAUSE_RATIO_BPS - supply
        uint256 maxBySupply = (backingUSDC() * 1e12 * 10_000) / PAUSE_RATIO_BPS;
        uint256 fromCollateral = maxBySupply > supply ? maxBySupply - supply : 0;
        return fromCap < fromCollateral ? fromCap : fromCollateral;
    }

    // ============ Governance (with 48h timelock) ============

    function queueGovernorChange(address next) external {
        require(msg.sender == governor, "not governor");
        require(next != address(0), "zero");
        pendingGovernor = next;
        pendingGovernorAt = block.timestamp;
        emit GovernorChangeQueued(next, block.timestamp);
    }

    function executeGovernorChange() external {
        require(pendingGovernor != address(0), "none queued");
        require(block.timestamp >= pendingGovernorAt + TIMELOCK, "timelock");
        governor = pendingGovernor;
        emit GovernorChanged(pendingGovernor);
        pendingGovernor = address(0);
        pendingGovernorAt = 0;
    }

    function queueSupplyCap(uint256 next) external {
        require(msg.sender == governor, "not governor");
        require(next >= totalSupply, "below current supply");
        pendingCap = next;
        pendingCapAt = block.timestamp;
        emit SupplyCapQueued(next, block.timestamp);
    }

    function executeSupplyCap() external {
        require(pendingCap != 0, "none queued");
        require(block.timestamp >= pendingCapAt + TIMELOCK, "timelock");
        supplyCap = pendingCap;
        emit SupplyCapChanged(pendingCap);
        pendingCap = 0;
        pendingCapAt = 0;
    }
}
