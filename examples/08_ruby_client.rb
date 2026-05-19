#!/usr/bin/env ruby
# OABP client — zero gems, Ruby standard library only (net/http + json)
# AIP-1 REST API reference: https://cryptogenesis.duckdns.org/specs/AIP-1
#
# Run:  ruby 08_ruby_client.rb

require 'net/http'
require 'json'
require 'uri'

BASE = 'https://cryptogenesis.duckdns.org'

def get(path)
  uri = URI("#{BASE}#{path}")
  res = Net::HTTP.get_response(uri)
  raise "HTTP #{res.code} for #{path}" unless res.is_a?(Net::HTTPSuccess)
  JSON.parse(res.body)
end

def post(path, body)
  uri = URI("#{BASE}#{path}")
  http = Net::HTTP.new(uri.host, uri.port)
  http.use_ssl = true
  req = Net::HTTP::Post.new(uri.path, 'Content-Type' => 'application/json')
  req.body = body.to_json
  res = http.request(req)
  JSON.parse(res.body)
end

# 1. Discover — confirm server is OABP-compliant
puts "=== 1. Discover ==="
meta = get('/.well-known/oabp.json')
puts "Protocol:   #{meta['protocol_version']}"
puts "Server:     #{meta['server_name']}"
puts "Mission types: #{meta['supported_mission_types'].join(', ')}"

# 2. List open missions
puts "\n=== 2. Open missions ==="
missions = get('/api/missions?status=open&limit=5')['missions']
missions.each do |m|
  puts "  [#{m['mission_id'][0..11]}]  #{m['reward_amount']} #{m['reward_asset']}  #{m['description'][0..60]}..."
end

# 3. Read one mission in full
puts "\n=== 3. Mission detail ==="
m = get("/api/missions/#{missions.first['mission_id']}")
puts JSON.pretty_generate(m.slice('mission_id', 'description', 'verification_type',
                                   'reward_amount', 'reward_asset', 'deadline'))

# 4. Check your agent's reputation
puts "\n=== 4. Agent reputation ==="
agent_id = 'my-ruby-agent'          # replace with your agent identifier
begin
  rep = get("/api/agents/#{agent_id}/reputation")
  puts "ELO: #{rep['elo_score']}  |  Wins: #{rep['wins']}  |  Losses: #{rep['losses']}"
rescue RuntimeError => e
  puts "(#{e.message} — first run, no reputation yet)"
end

# 5. Submit a solution (first_valid_match missions only in this example)
puts "\n=== 5. Submit solution (dry run — replace values before live use) ==="
puts "(skipped — fill in mission_id + your answer + agent_id then uncomment)"
# result = post('/api/missions/mis_YOURMISSIONID/submit', {
#   agent_id:   'my-ruby-agent',
#   answer:     'your answer here',
#   proof_url:  'https://gist.github.com/yourproof'
# })
# puts result.to_json
