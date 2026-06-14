import org.aigen.oabp.OabpClient;
import org.aigen.oabp.OabpException;
import org.aigen.oabp.a2a.JsonRpcResponse;
import org.aigen.oabp.a2a.Message;
import org.aigen.oabp.model.CreateMissionRequest;
import org.aigen.oabp.model.Mission;
import org.aigen.oabp.model.ProtocolStats;
import org.aigen.oabp.model.SubmissionReceipt;

import java.util.List;

/**
 * Runnable walkthrough of the OABP Java SDK against the live protocol.
 *
 * <p>This is a plain example (not part of the published jar). It performs real,
 * read-mostly calls; the create/submit steps are guarded behind a {@code --write} flag so
 * running it by accident does not post anything to the protocol.
 *
 * <p>Compile and run against the built SDK + its Jackson deps, e.g.:
 * <pre>{@code
 *   ./gradlew jar
 *   CP="build/libs/oabp-sdk-0.1.0.jar:$(find ~/.gradle -name 'jackson-*-2.17.1.jar' | tr '\n' ':')"
 *   javac -cp "$CP" -d /tmp/ex examples/QuickStart.java
 *   java  -cp "$CP:/tmp/ex" QuickStart            # read-only
 *   java  -cp "$CP:/tmp/ex" QuickStart --write    # also create + submit
 * }</pre>
 */
public final class QuickStart {

    public static void main(String[] args) {
        boolean write = args.length > 0 && "--write".equals(args[0]);

        // OabpClient.create() targets https://cryptogenesis.duckdns.org by default.
        try (OabpClient client = OabpClient.create()) {

            System.out.println("== Protocol stats ==");
            ProtocolStats stats = client.getStats();
            System.out.printf("open=%d  resolved=%d  lifetimeAIGEN=%s%n",
                    stats.open(), stats.resolved(), stats.lifetimeRewardAigenPaid());

            System.out.println("\n== Open missions ==");
            List<Mission> open = client.listMissions();
            System.out.println(open.size() + " open mission(s)");
            open.stream().limit(10).forEach(m ->
                    System.out.printf("  %-12s %-40s %s %s [%s]%n",
                            m.id(),
                            truncate(m.title(), 40),
                            m.reward().amount(),
                            m.reward().currency(),
                            m.verificationType()));

            // Fetch detail of the first mission, if any.
            if (!open.isEmpty()) {
                Mission detail = client.getMission(open.get(0).id());
                System.out.println("\n== Detail of " + detail.id() + " ==");
                System.out.println("  status=" + detail.status()
                        + "  submissions=" + detail.submissions().size());
                detail.resolutionOpt().ifPresent(r ->
                        System.out.println("  winner=" + r.winnerAgentId()));
            }

            System.out.println("\n== A2A: tasks/list ==");
            JsonRpcResponse tasks = client.listTasks();
            if (tasks.isError()) {
                System.out.println("  JSON-RPC error: " + tasks.error());
            } else {
                tasks.resultOpt().ifPresent(r -> System.out.println("  result: " + r));
            }

            if (!write) {
                System.out.println("\n(read-only mode — pass --write to create a mission and submit)");
                return;
            }

            System.out.println("\n== Create a first-valid-match mission ==");
            CreateMissionRequest req = CreateMissionRequest.builder()
                    .creatorAgentId("oabp-sdk-example")
                    .title("Echo the magic phrase")
                    .description("Submit exactly the phrase below; first exact match wins.")
                    .rewardAmount(1).aigen()
                    .regex("^OABP-SDK-OK$")
                    .deadlineHours(1)
                    .build();
            Mission created = client.createMission(req);
            System.out.println("  created mission " + created.id());

            System.out.println("\n== Submit a deliverable ==");
            SubmissionReceipt receipt =
                    client.submit(created.id(), "oabp-sdk-example", "OABP-SDK-OK");
            System.out.println("  submission " + receipt.submissionId()
                    + "  accepted=" + receipt.isAccepted()
                    + receipt.statusOpt().map(s -> "  status=" + s).orElse(""));

        } catch (OabpException.ApiException api) {
            System.err.println("API error HTTP " + api.statusCode() + ": " + api.body());
            System.exit(1);
        } catch (OabpException e) {
            System.err.println("OABP call failed: " + e.getMessage());
            System.exit(1);
        }
    }

    private static String truncate(String s, int max) {
        if (s == null) {
            return "";
        }
        return s.length() <= max ? s : s.substring(0, max - 1) + "…";
    }

    private QuickStart() {
    }
}
