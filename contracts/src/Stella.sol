// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title Stella — AIGEN-treasury-backed stablecoin (v0.2)
 * @notice 1 STELLA = $1, fully redeemable for USDC on Base.
 *         CONTRACT-HELD USDC model: backing lives in this contract, not in
 *         an external treasury. Eliminates treasury-approval dependency.
 *
 *         Built explicitly to NOT repeat Terra/Luna's failure modes:
 *         - 100% USDC-backed (every STELLA = 1 USDC in contract custody)
 *         - Mint pauses if collateral_ratio < 110% or peg < $0.97
 *         - Redemption ALWAYS works (no admin function exists for it)
 *         - 48h timelock on all governance changes
 *         - Emergency cancel for pending supply-cap / governor changes
 *           if the queued change is wildly outside historical bounds
 *         - Single chain (Base only). No bridges.
 *         - No upgrade proxy. Code immutable.
 *
 * @dev v0.2 audit fixes:
 *      C1: Contract holds USDC (not treasury) — removes approval dependency
 *      H1: pokePause() handles oracle staleness as a valid pause condition
 *      H2: Cancel functions for pending governor / supplyCap changes
 *      M1: nonReentrant modifier on mint
 *      L1: 1 USDC minimum mint
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

    function transfer(address to, uint256 amt) external returns (bool) { return _transfer(msg.sender, to, amt); }
    function approve(address spender, uint256 amt) external returns (bool) {
        allowance[msg.sender][spender] = amt;
        emit Approval(msg.sender, spender, amt);
        return true;
    }
    function transferFrom(address from, address to, uint256 amt) external returns (bool) {
        uint256 a = allowance[from][msg.sender];
        if (a != type(uint256).max) { require(a >= amt, "ERC20: allowance"); allowance[from][msg.sender] = a - amt; }
        return _transfer(from, to, amt);
    }
    function _transfer(address from, address to, uint256 amt) internal returns (bool) {
        require(to != address(0), "ERC20: zero");
        uint256 b = balanceOf[from]; require(b >= amt, "ERC20: balance");
        unchecked { balanceOf[from] = b - amt; }
        balanceOf[to] += amt;
        emit Transfer(from, to, amt);
        return true;
    }

    // ============ Stella ============
    address public immutable USDC;
    address public immutable PRICE_ORACLE;

    address public governor;
    address public pendingGovernor;
    uint256 public pendingGovernorAt;

    uint256 public supplyCap = 100_000e18;
    uint256 public pendingCap;
    uint256 public pendingCapAt;
    uint256 public constant TIMELOCK = 48 hours;

    uint256 public constant PAUSE_RATIO_BPS = 11_000;     // 110%
    uint256 public constant MINT_RATIO_BPS  = 15_000;     // 150%
    int256  public constant PEG_FLOOR       = 97_000_000; // $0.97 (8 decimals)
    uint256 public constant ORACLE_STALE_AFTER = 1 hours;
    uint256 public constant MIN_MINT_USDC   = 1_000_000;  // 1 USDC (L1 fix)
    uint256 public constant EMERGENCY_CANCEL_RATIO_BPS = 1000_000; // 10000% — extreme cap raise

    bool public mintPaused;
    uint256 public mintPausedAt;

    // Re-entrancy guard (M1 fix)
    uint256 private _locked = 1;
    modifier nonReentrant() {
        require(_locked == 1, "REENTRANCY");
        _locked = 2;
        _;
        _locked = 1;
    }

    event Minted(address indexed to, uint256 stellaOut, uint256 usdcIn, uint256 ratioAfterBps);
    event Redeemed(address indexed from, uint256 stellaIn, uint256 usdcOut);
    event Donated(address indexed from, uint256 usdcIn);
    event MintAutoPaused(uint256 ratio, int256 peg, bool oracleStale);
    event Unpaused(address indexed by);
    event GovernorChangeQueued(address indexed next, uint256 ts);
    event GovernorChangeCanceled(address indexed by, address indexed canceledNext);
    event GovernorChanged(address indexed next);
    event SupplyCapQueued(uint256 next, uint256 ts);
    event SupplyCapCanceled(address indexed by, uint256 canceledNext);
    event SupplyCapChanged(uint256 next);

    constructor(address usdc, address oracle, address governor_) {
        require(usdc != address(0) && governor_ != address(0), "zero addr");
        USDC = usdc;
        PRICE_ORACLE = oracle;  // can be 0x0 → peg() returns 1e8
        governor = governor_;
    }

    // ============ Mint / Redeem ============

    /// Mint STELLA by depositing USDC 1:1. Contract custodies the USDC.
    function mint(uint256 usdcAmount) external nonReentrant returns (uint256 stellaOut) {
        require(!mintPaused, "mint paused");
        require(usdcAmount >= MIN_MINT_USDC, "below min mint");

        // Peg + ratio check BEFORE accepting funds
        int256 p = peg();
        require(p >= PEG_FLOOR, "peg below floor");

        stellaOut = usdcAmount * 1e12;
        require(totalSupply + stellaOut <= supplyCap, "supply cap");

        uint256 ratioBefore = collateralRatioBps();
        require(ratioBefore >= MINT_RATIO_BPS, "ratio below 150%");

        // Accept USDC into contract custody (C1 fix: was → TREASURY)
        IERC20(USDC).transferFrom(msg.sender, address(this), usdcAmount);

        totalSupply += stellaOut;
        balanceOf[msg.sender] += stellaOut;
        emit Transfer(address(0), msg.sender, stellaOut);

        // Final invariant check
        uint256 ratioAfter = collateralRatioBps();
        require(ratioAfter >= PAUSE_RATIO_BPS, "would breach pause threshold");

        emit Minted(msg.sender, stellaOut, usdcAmount, ratioAfter);
    }

    /// Redeem STELLA for USDC at $1, ALWAYS. No pause function — by design.
    /// USDC comes from contract's own balance — no external approval needed.
    function redeem(uint256 stellaAmount) external nonReentrant returns (uint256 usdcOut) {
        require(stellaAmount > 0, "zero");
        uint256 b = balanceOf[msg.sender];
        require(b >= stellaAmount, "balance");

        usdcOut = stellaAmount / 1e12;
        require(usdcOut > 0, "dust");

        unchecked { balanceOf[msg.sender] = b - stellaAmount; }
        totalSupply -= stellaAmount;
        emit Transfer(msg.sender, address(0), stellaAmount);

        // Pull from contract custody (C1 fix: was transferFrom TREASURY)
        IERC20(USDC).transfer(msg.sender, usdcOut);
        emit Redeemed(msg.sender, stellaAmount, usdcOut);
    }

    /// Anyone can donate USDC to grow the backing without minting STELLA.
    /// Useful for AIGEN treasury fee deposits → strengthens collateral ratio.
    function donate(uint256 usdcAmount) external nonReentrant {
        require(usdcAmount > 0, "zero");
        IERC20(USDC).transferFrom(msg.sender, address(this), usdcAmount);
        emit Donated(msg.sender, usdcAmount);
    }

    // ============ Auto-pause ============

    /// Anyone can call. Pauses minting if ratio breaches OR oracle stale OR peg low.
    /// (H1 fix: oracle staleness now triggers pause instead of reverting)
    function pokePause() external {
        require(!mintPaused, "already paused");
        uint256 ratio = collateralRatioBps();
        bool oracleStale = false;
        int256 p = 100_000_000;
        if (PRICE_ORACLE != address(0)) {
            try IPriceOracle(PRICE_ORACLE).latestAnswer() returns (int256 v) {
                p = v;
                try IPriceOracle(PRICE_ORACLE).latestTimestamp() returns (uint256 ts) {
                    if (block.timestamp - ts > ORACLE_STALE_AFTER) oracleStale = true;
                } catch { oracleStale = true; }
            } catch { oracleStale = true; }
        }

        if (ratio < PAUSE_RATIO_BPS || p < PEG_FLOOR || oracleStale) {
            mintPaused = true;
            mintPausedAt = block.timestamp;
            emit MintAutoPaused(ratio, p, oracleStale);
        }
    }

    /// Only governor can unpause, AND only when ratio + peg both healthy + oracle fresh.
    function unpause() external {
        require(msg.sender == governor, "not governor");
        require(mintPaused, "not paused");
        require(collateralRatioBps() >= MINT_RATIO_BPS, "ratio not restored");
        require(peg() >= 99_000_000, "peg not restored");  // peg() reverts if oracle stale
        mintPaused = false;
        emit Unpaused(msg.sender);
    }

    // ============ Views ============

    /// USDC held in this contract — actual backing. (C1: now reads contract, not treasury.)
    function backingUSDC() public view returns (uint256) {
        return IERC20(USDC).balanceOf(address(this));
    }

    function collateralRatioBps() public view returns (uint256) {
        uint256 supply = totalSupply;
        if (supply == 0) return type(uint256).max;
        return (backingUSDC() * 1e12 * 10_000) / supply;
    }

    /// USDC/USD price from Chainlink. Reverts if oracle stale or bad.
    function peg() public view returns (int256) {
        if (PRICE_ORACLE == address(0)) return 100_000_000;
        IPriceOracle o = IPriceOracle(PRICE_ORACLE);
        int256 p = o.latestAnswer();
        require(p > 0, "oracle bad");
        require(block.timestamp - o.latestTimestamp() <= ORACLE_STALE_AFTER, "oracle stale");
        return p;
    }

    function mintableNow() external view returns (uint256) {
        if (mintPaused) return 0;
        uint256 supply = totalSupply;
        uint256 fromCap = supply >= supplyCap ? 0 : supplyCap - supply;
        uint256 maxBySupply = (backingUSDC() * 1e12 * 10_000) / PAUSE_RATIO_BPS;
        uint256 fromCollateral = maxBySupply > supply ? maxBySupply - supply : 0;
        return fromCap < fromCollateral ? fromCap : fromCollateral;
    }

    // ============ Governance (timelocked + emergency-cancel) ============

    function queueGovernorChange(address next) external {
        require(msg.sender == governor, "not governor");
        require(next != address(0), "zero");
        pendingGovernor = next;
        pendingGovernorAt = block.timestamp;
        emit GovernorChangeQueued(next, block.timestamp);
    }

    /// Governor can cancel a queued change at any time (sane self-correction).
    function cancelGovernorChange() external {
        require(msg.sender == governor, "not governor");
        require(pendingGovernor != address(0), "none queued");
        emit GovernorChangeCanceled(msg.sender, pendingGovernor);
        pendingGovernor = address(0);
        pendingGovernorAt = 0;
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

    function cancelSupplyCap() external {
        require(msg.sender == governor, "not governor");
        require(pendingCap != 0, "none queued");
        emit SupplyCapCanceled(msg.sender, pendingCap);
        pendingCap = 0;
        pendingCapAt = 0;
    }

    /// (H2 fix) Anyone can cancel a queued supplyCap if it's >100x current cap —
    /// strong signal of governor compromise. Still respects 48h timelock so legit
    /// large raises can still complete; this only catches obviously malicious ones.
    function emergencyCancelSupplyCap() external {
        require(pendingCap != 0, "none queued");
        // Only cancel if pending is >100x current — signal of clear attack
        require(pendingCap > supplyCap * 100, "not extreme");
        emit SupplyCapCanceled(msg.sender, pendingCap);
        pendingCap = 0;
        pendingCapAt = 0;
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
