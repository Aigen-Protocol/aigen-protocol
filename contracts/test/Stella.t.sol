// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/Stella.sol";

contract MockUSDC {
    string  public name = "USDC";
    uint8   public decimals = 6;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    function approve(address s, uint256 a) external returns (bool) { allowance[msg.sender][s] = a; return true; }
    function transfer(address t, uint256 a) external returns (bool) { balanceOf[msg.sender] -= a; balanceOf[t] += a; return true; }
    function transferFrom(address f, address t, uint256 a) external returns (bool) {
        if (allowance[f][msg.sender] != type(uint256).max) allowance[f][msg.sender] -= a;
        balanceOf[f] -= a; balanceOf[t] += a; return true;
    }
    function mint(address to, uint256 amt) external { balanceOf[to] += amt; totalSupply += amt; }
}

contract StellaTest is Test {
    Stella stella;
    MockUSDC usdc;
    address treasury = address(0xDa429f2034b62b8722713873dE3C045eec390d8F);
    address governor = address(0xCAFE);
    address alice    = address(0xA11CE);

    function setUp() public {
        usdc = new MockUSDC();
        stella = new Stella(address(usdc), treasury, address(0), governor);
        // Treasury approves Stella contract for redemptions
        vm.prank(treasury);
        usdc.approve(address(stella), type(uint256).max);
        // Bootstrap treasury with $1000 USDC (over-collateralizes)
        usdc.mint(treasury, 1_000_000_000); // 1000 USDC (6 decimals)
    }

    function test_initial_state() public view {
        assertEq(stella.totalSupply(), 0);
        assertEq(stella.collateralRatioBps(), type(uint256).max);
        assertEq(stella.supplyCap(), 100_000e18);
        assertEq(stella.peg(), 100_000_000);
        assertEq(stella.mintPaused(), false);
    }

    function test_mint_basic() public {
        usdc.mint(alice, 100e6); // alice has 100 USDC
        vm.prank(alice);
        usdc.approve(address(stella), 100e6);
        vm.prank(alice);
        uint256 out = stella.mint(100e6); // mint 100 STELLA
        assertEq(out, 100e18);
        assertEq(stella.balanceOf(alice), 100e18);
        assertEq(stella.totalSupply(), 100e18);
        // After: backing = 1000 + 100 = 1100 USDC, supply = 100 STELLA
        // Ratio = 1100/100 = 1100% = 110000 bps
        assertEq(stella.collateralRatioBps(), 110_000);
    }

    function test_mint_reverts_when_under_collateralized() public {
        // Make treasury empty
        vm.prank(treasury);
        usdc.transfer(address(0xdead), 1_000_000_000);
        usdc.mint(alice, 100e6);
        vm.prank(alice);
        usdc.approve(address(stella), 100e6);
        // First mint when supply=0 → collateralRatioBps returns max → passes initial check
        // But after the mint, ratio = (0 + 100*1e12*10000)/(100e18) = 1e16 / 100e18 = 0.0001 → 1 bps
        // Wait, let me reconsider. Backing AFTER user sends = 100 USDC (treasury was empty before).
        // Supply = 100e18. Ratio = (100*1e12*10000)/100e18 = 1e18 / 100e18 = 0.01 → 100 bps = 1%
        // That's below MINT_RATIO_BPS (15000) but the check is BEFORE the transfer.
        // Before: backing = 0, supply = 0 → ratio = max → passes.
        // After: ratio = 100 bps → fails the "would breach pause threshold" check.
        vm.prank(alice);
        vm.expectRevert("would breach pause threshold");
        stella.mint(100e6);
    }

    function test_redeem_basic() public {
        // Setup: alice mints 100 STELLA
        usdc.mint(alice, 100e6);
        vm.prank(alice);
        usdc.approve(address(stella), 100e6);
        vm.prank(alice);
        stella.mint(100e6);

        // Alice redeems 50 STELLA → should get 50 USDC back
        vm.prank(alice);
        uint256 out = stella.redeem(50e18);
        assertEq(out, 50e6);
        assertEq(usdc.balanceOf(alice), 50e6);
        assertEq(stella.totalSupply(), 50e18);
        assertEq(stella.balanceOf(alice), 50e18);
    }

    function test_redeem_works_even_when_minting_paused() public {
        // Mint then pause
        usdc.mint(alice, 100e6);
        vm.prank(alice);
        usdc.approve(address(stella), 100e6);
        vm.prank(alice);
        stella.mint(100e6);
        // Drain treasury to trigger auto-pause condition
        vm.prank(treasury);
        usdc.transfer(address(0xdead), 1_050_000_000); // leave less than 110% backing
        // Now collateralRatioBps should be ~50e6 / 100e18 → very low. Anyone can poke.
        stella.pokePause();
        assertEq(stella.mintPaused(), true);
        // But redeem still works (key safety property)
        vm.prank(alice);
        stella.redeem(50e18);
        assertEq(stella.balanceOf(alice), 50e18);
    }

    function test_supply_cap_timelock() public {
        vm.prank(governor);
        stella.queueSupplyCap(200_000e18);
        assertEq(stella.supplyCap(), 100_000e18); // not yet
        // Try to execute too early
        vm.expectRevert("timelock");
        stella.executeSupplyCap();
        // Wait 48h
        vm.warp(block.timestamp + 48 hours + 1);
        stella.executeSupplyCap();
        assertEq(stella.supplyCap(), 200_000e18);
    }

    function test_only_governor_can_unpause() public {
        // Trigger pause
        usdc.mint(alice, 100e6);
        vm.prank(alice);
        usdc.approve(address(stella), 100e6);
        vm.prank(alice);
        stella.mint(100e6);
        vm.prank(treasury);
        usdc.transfer(address(0xdead), 1_050_000_000);
        stella.pokePause();
        // Random caller cannot unpause
        vm.prank(alice);
        vm.expectRevert("not governor");
        stella.unpause();
        // Even governor cannot if conditions not restored
        vm.prank(governor);
        vm.expectRevert("ratio not restored");
        stella.unpause();
        // Restore conditions
        usdc.mint(treasury, 200e6); // bring back to 200 USDC backing for 100 STELLA = 200%
        // (Plus the 50 still from earlier)
        // ratio = ~250e6 * 1e12 * 10000 / 100e18 = 2.5e22 / 1e20 = 250 → wait that's wrong
        // Actually: 250e6 in 6-decimal USDC = 250_000_000. *1e12 = 2.5e20. *10_000 = 2.5e24. / 1e20 = 25_000 bps = 250%
        // OK, that's above 15000 = 150%. Good.
        vm.prank(governor);
        stella.unpause();
        assertEq(stella.mintPaused(), false);
    }
}
