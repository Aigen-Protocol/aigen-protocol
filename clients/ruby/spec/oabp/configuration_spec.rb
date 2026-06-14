# frozen_string_literal: true

require "spec_helper"

RSpec.describe Oabp::Configuration do
  it "defaults to the public AIGEN node" do
    expect(described_class.new.base_url).to eq("https://cryptogenesis.duckdns.org")
  end

  it "strips a trailing slash from the base url" do
    config = described_class.new
    config.base_url = "https://oabp.test/"
    expect(config.normalized_base_url).to eq("https://oabp.test")
  end

  it "rejects a blank base url" do
    config = described_class.new
    config.base_url = "  "
    expect { config.normalized_base_url }.to raise_error(Oabp::ConfigurationError, /required/)
  end

  it "rejects a non-http base url" do
    config = described_class.new
    config.base_url = "ftp://oabp.test"
    expect { config.normalized_base_url }.to raise_error(Oabp::ConfigurationError, /http/)
  end

  it "applies overrides while ignoring nils" do
    config = described_class.new
    copy = config.dup_with_overrides(base_url: "https://x.test", agent_id: nil, timeout: 5)
    expect(copy.base_url).to eq("https://x.test")
    expect(copy.timeout).to eq(5)
    expect(config.base_url).to eq("https://cryptogenesis.duckdns.org") # original untouched
  end

  it "raises on an unknown override key" do
    expect { described_class.new.dup_with_overrides(nope: 1) }
      .to raise_error(Oabp::ConfigurationError, /unknown option/)
  end

  it "does not share default_headers between copies" do
    config = described_class.new
    copy = config.dup_with_overrides({})
    copy.default_headers["X-Test"] = "1"
    expect(config.default_headers).to be_empty
  end
end

RSpec.describe Oabp do
  it "memoizes a module-level configuration" do
    expect(described_class.configuration).to be(described_class.configuration)
  end

  it "configures via a block" do
    described_class.configure { |c| c.agent_id = "did:agent:zed" }
    expect(described_class.configuration.agent_id).to eq("did:agent:zed")
  end

  it "builds a default client and fresh clients" do
    expect(described_class.client).to be_a(Oabp::Client)
    expect(described_class.new_client(base_url: "https://x.test")).to be_a(Oabp::Client)
  end
end
