// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/Stella.sol";

/**
 * Deploy STELLA on Base mainnet (chain id 8453).
 *
 * Required env vars:
 *   PRIVATE_KEY      — deployer key (must have ~$0.50 in ETH for gas)
 *   GOVERNOR_ADDRESS — multisig address that becomes initial governor
 *
 * Constants for Base:
 *   USDC   = 0x833589fcd6edb6e08f4c7c32d4f71b54bda02913
 *   ORACLE = 0x7e860098F58bBFC8648a4311b374B1D669a2bc6B  (Chainlink USDC/USD)
 *
 * Treasury (AIGEN) = 0xDa429f2034b62b8722713873dE3C045eec390d8F
 *
 * After deployment:
 *   1. Treasury MUST call usdc.approve(stella, type(uint256).max) so redemptions work.
 *   2. Verify on Basescan.
 *   3. Update https://cryptogenesis.duckdns.org/api/stella/contract with the address.
 *   4. Announce.
 *
 * Estimated gas: ~2.5M units = ~$0.20 on Base mainnet.
 *
 * Run:
 *   forge script script/Deploy.s.sol --rpc-url https://mainnet.base.org \
 *       --private-key $PRIVATE_KEY --broadcast --verify --etherscan-api-key $BASESCAN_KEY
 */
contract DeployStella is Script {
    address constant USDC_BASE = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;
    address constant CHAINLINK_USDC_USD_BASE = 0x7e860098F58bBFC8648a4311b374B1D669a2bc6B;
    address constant TREASURY = 0xDa429f2034b62b8722713873dE3C045eec390d8F;

    function run() external returns (Stella stella) {
        address governor = vm.envAddress("GOVERNOR_ADDRESS");
        uint256 pk = vm.envUint("PRIVATE_KEY");

        vm.startBroadcast(pk);
        // v0.2: contract-held USDC model — no treasury parameter
        stella = new Stella(USDC_BASE, CHAINLINK_USDC_USD_BASE, governor);
        vm.stopBroadcast();

        console2.log("STELLA deployed at:", address(stella));
        console2.log("USDC:", USDC_BASE);
        console2.log("Oracle:", CHAINLINK_USDC_USD_BASE);
        console2.log("Governor:", governor);
        console2.log("");
        console2.log("Next steps:");
        console2.log("  1. (Optional) AIGEN treasury donates initial backing:");
        console2.log("     cast send", USDC_BASE, "approve(address,uint256) <STELLA>", "<amount>");
        console2.log("     cast send <STELLA> donate(uint256) <amount>");
        console2.log("  2. Update STELLA_CONTRACT in scanner.py with the deployed address");
        console2.log("  3. Verify on Basescan");
    }
}
