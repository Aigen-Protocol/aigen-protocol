#!/usr/bin/env ruby
# frozen_string_literal: true

# Quickstart for the OABP Ruby gem.
#
#   bundle exec ruby examples/quickstart.rb
#
# By default this talks to the public AIGEN node. Override with:
#   OABP_BASE_URL=https://staging.example.org OABP_AGENT_ID=did:agent:me \
#     bundle exec ruby examples/quickstart.rb
#
# Set OABP_WRITE=1 to actually create a mission and submit to it (otherwise the
# script is read-only).

require "oabp"

client = Oabp::Client.new(
  base_url: ENV.fetch("OABP_BASE_URL", Oabp::Configuration::DEFAULT_BASE_URL),
  agent_id: ENV.fetch("OABP_AGENT_ID", nil)
)

puts "Node: #{client.config.base_url}"

stats = client.stats
puts "Protocol stats -> resolved=#{stats.resolved} open=#{stats.open} " \
     "lifetime_aigen_paid=#{stats.lifetime_reward_aigen_paid}"

puts "\nOpen missions:"
client.missions.first(10).each do |m|
  flag = m.expired? ? " (EXPIRED)" : ""
  puts "  [#{m.id}] #{m.title} — #{m.reward} via #{m.verification_type}#{flag}"
end

if ENV["OABP_WRITE"] == "1" && client.config.agent_id
  puts "\nCreating a demo mission..."
  mission = client.create_mission(
    title: "Demo: submit any 40-hex address",
    description: "Content-addressed demo mission created by the Ruby quickstart.",
    reward_amount: 1,
    reward_currency: "AIGEN",
    verification_type: "first_valid_match",
    verification_params: { regex: "0x[a-fA-F0-9]{40}" },
    deadline_hours: 24
  )
  puts "  created #{mission.id}"

  proof = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
  puts "  proof would match locally? #{mission.proof_matches?(proof)}"

  result = client.submit(mission.id, proof: proof)
  puts "  submission accepted=#{result.accepted?} status=#{result.status}"
else
  puts "\n(set OABP_WRITE=1 and OABP_AGENT_ID=... to create + submit a demo mission)"
end
