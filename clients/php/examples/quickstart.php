<?php

declare(strict_types=1);

/**
 * End-to-end example against the live OABP / AIGEN protocol.
 *
 * Usage:
 *   composer install
 *   php examples/quickstart.php
 *
 * It only reads by default (list missions, fetch one, read stats, fetch the
 * agent card). Set CREATE=1 in the environment to also create a demo mission
 * and submit a deliverable to it.
 */

require __DIR__ . '/../vendor/autoload.php';

use Aigen\Oabp\Dto\CreateMissionRequest;
use Aigen\Oabp\Enum\RewardCurrency;
use Aigen\Oabp\Exception\OabpException;
use Aigen\Oabp\OabpClient;

$client = new OabpClient(
    baseUrl: getenv('OABP_BASE_URL') ?: OabpClient::DEFAULT_BASE_URL,
    apiKey: getenv('OABP_API_KEY') ?: null,
);

try {
    // 1. Protocol-wide stats.
    $stats = $client->getStats();
    printf(
        "Stats: %d open, %d resolved, %.0f AIGEN paid lifetime\n",
        $stats->open,
        $stats->resolved,
        $stats->lifetimeRewardAigenPaid,
    );

    // 2. List open missions.
    $missions = $client->listMissions();
    printf("Open missions: %d\n", count($missions));
    foreach (array_slice($missions, 0, 5) as $m) {
        printf(
            "  [%s] %s — reward %s — verify=%s — %d submissions\n",
            $m->id ?? '?',
            $m->title ?? '(untitled)',
            $m->reward !== null ? (string) $m->reward : 'n/a',
            $m->verificationType?->value ?? 'unknown',
            $m->submissionCount(),
        );
    }

    // 3. Fetch one mission in detail.
    if ($missions !== [] && $missions[0]->id !== null) {
        $detail = $client->getMission($missions[0]->id);
        printf(
            "\nDetail of mission %s: status=%s, %d submissions, resolved=%s\n",
            $detail->id ?? '?',
            $detail->status ?? 'unknown',
            $detail->submissionCount(),
            $detail->resolution !== null ? 'yes' : 'no',
        );
    }

    // 4. Read the signed agent card (A2A discovery).
    $card = $client->getAgentCard();
    printf("\nAgent card name: %s\n", is_scalar($card['name'] ?? null) ? (string) $card['name'] : 'n/a');

    // 5. A2A JSON-RPC: list tasks.
    $tasks = $client->a2aListTasks();
    if ($tasks->isError()) {
        printf("A2A tasks/list error: %s\n", (string) $tasks->errorMessage());
    } else {
        echo "A2A tasks/list OK\n";
    }

    // 6. Optionally create a mission and submit to it.
    if (getenv('CREATE') === '1') {
        $agentId = getenv('OABP_AGENT_ID') ?: 'oabp-php-sdk-demo';

        $created = $client->createMission(CreateMissionRequest::firstValidMatch(
            creatorAgentId: $agentId,
            title: 'SDK demo: echo the passphrase',
            description: 'Submit the exact passphrase to win.',
            rewardAmount: 1.0,
            rewardCurrency: RewardCurrency::Aigen,
            regex: '^OABP-PHP-DEMO$',
            deadlineHours: 24,
        ));
        printf("\nCreated mission %s\n", $created->id ?? '?');

        if ($created->id !== null) {
            $result = $client->submit($created->id, $agentId, 'OABP-PHP-DEMO');
            printf(
                "Submitted: accepted=%s, verified=%s, winner=%s\n",
                $result->accepted ? 'yes' : 'no',
                $result->verified === null ? 'n/a' : ($result->verified ? 'yes' : 'no'),
                $result->isWinner() ? 'yes' : 'no',
            );
        }
    }
} catch (OabpException $e) {
    fwrite(STDERR, 'OABP error: ' . $e->getMessage() . "\n");
    exit(1);
}
