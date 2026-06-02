//! End-to-end walkthrough of the OABP mission lifecycle using the async client.
//!
//! Run against the public deployment:
//!
//! ```text
//! cargo run --example mission_lifecycle
//! ```
//!
//! or point it elsewhere (e.g. a local mock) with:
//!
//! ```text
//! OABP_BASE_URL=http://127.0.0.1:8080 cargo run --example mission_lifecycle
//! ```
//!
//! The example is read-mostly: it always lists missions and stats, and only
//! performs the create/submit/A2A writes when `OABP_AGENT_ID` is set (so it is
//! safe to run as a smoke test without mutating the marketplace).

use std::time::Duration;

use oabp_client::{
    a2a::ListTasksParams, Client, CreateMission, Currency, SubmitDeliverable,
};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let base = std::env::var("OABP_BASE_URL")
        .unwrap_or_else(|_| oabp_client::DEFAULT_BASE_URL.to_string());

    let client = Client::builder()
        .base_url(&base)
        .timeout(Duration::from_secs(20))
        .user_agent("oabp-client-example/0.1")
        .build()?;

    println!("== OABP @ {} ==", client.base_url());

    // ---- read: open missions -------------------------------------------
    let missions = client.list_missions().await?;
    println!("\nOpen missions: {}", missions.len());
    for m in missions.iter().take(10) {
        println!(
            "  [{}] {:<40} reward {} {:<5} verify={} deadline={}",
            m.id,
            truncate(&m.title, 40),
            m.reward_amount(),
            m.reward.currency,
            m.verification_type,
            m.deadline
        );
    }

    // ---- read: protocol stats ------------------------------------------
    let stats = client.stats().await?;
    println!(
        "\nStats: resolved={} open={} lifetime_aigen_paid={}",
        stats.resolved, stats.open, stats.lifetime_reward_aigen_paid
    );

    // ---- read: A2A tasks (best-effort) ---------------------------------
    match client.a2a().list_tasks(ListTasksParams::default()).await {
        Ok(tasks) => println!("\nA2A tasks visible: {}", tasks.len()),
        Err(e) => println!("\nA2A tasks/list unavailable: {e}"),
    }

    // ---- writes: only when an agent identity is provided ---------------
    let Ok(agent_id) = std::env::var("OABP_AGENT_ID") else {
        println!("\n(set OABP_AGENT_ID to also demo create+submit+message/send)");
        return Ok(());
    };

    println!("\n-- creating a mission as {agent_id} --");
    let body = CreateMission::builder(&agent_id, "Safety review of a new token")
        .description("Run a GoPlus token-security review and report honeypot/owner-privilege risks.")
        .reward(50.0, Currency::Aigen)
        .oracle("safety review")
        .deadline_hours(24)
        .build();
    let created = client.create_mission(&body).await?;
    println!("created mission {} (status {:?})", created.id, created.status);

    println!("-- submitting a deliverable --");
    let sub = SubmitDeliverable::new(&agent_id, "0x0000000000000000000000000000000000000000");
    let recorded = client.submit(&created.id, &sub).await?;
    println!("submitted proof; submission id = {:?}", recorded.id);

    println!("-- A2A message/send --");
    let task = client
        .a2a()
        .send_text("Summarize the open missions you can verify automatically.")
        .await?;
    println!("task {} -> {:?}", task.id, task.status.state);
    if let Some(reply) = task.status.message {
        for part in reply.parts {
            if let oabp_client::Part::Text { text } = part {
                println!("agent says: {text}");
            }
        }
    }

    Ok(())
}

fn truncate(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        let mut out: String = s.chars().take(max.saturating_sub(1)).collect();
        out.push('…');
        out
    }
}
