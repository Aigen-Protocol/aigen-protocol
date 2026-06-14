# frozen_string_literal: true

module Oabp
  # Base error for every exception raised by the gem.
  class Error < StandardError; end

  # Raised when the client is misconfigured (e.g. a malformed base URL).
  class ConfigurationError < Error; end

  # Raised when an argument supplied to a client method is invalid.
  class ValidationError < Error; end

  # Base class for any non-2xx HTTP response returned by the API.
  #
  # Carries the HTTP +status+, the raw response +body+ (already parsed when it
  # was JSON), and the originating request +method+/+path+ for debugging.
  class ApiError < Error
    attr_reader :status, :body, :request_method, :path

    def initialize(message = nil, status: nil, body: nil, request_method: nil, path: nil)
      @status = status
      @body = body
      @request_method = request_method
      @path = path
      super(message || default_message)
    end

    private

    def default_message
      detail = extract_detail
      base = "OABP API request failed"
      base += " (#{request_method.to_s.upcase} #{path})" if path
      base += " -> HTTP #{status}" if status
      base += ": #{detail}" if detail
      base
    end

    def extract_detail
      return body unless body.is_a?(Hash)

      body["error"] || body["message"] || body["detail"]
    end
  end

  # 400 — malformed request.
  class BadRequestError < ApiError; end

  # 401 / 403 — authentication or authorization failure.
  class AuthenticationError < ApiError; end

  # 404 — resource not found (e.g. unknown mission id).
  class NotFoundError < ApiError; end

  # 409 — conflict (e.g. mission already resolved, duplicate submission).
  class ConflictError < ApiError; end

  # 422 — semantically invalid request (e.g. proof failed verification).
  class UnprocessableEntityError < ApiError; end

  # 429 — rate limited.
  class RateLimitError < ApiError; end

  # 5xx — server-side failure.
  class ServerError < ApiError; end

  # Raised when the transport itself fails (timeout, DNS, connection reset).
  class ConnectionError < Error; end

  # Maps an HTTP status code to the most specific {ApiError} subclass.
  module ErrorFactory
    STATUS_MAP = {
      400 => BadRequestError,
      401 => AuthenticationError,
      403 => AuthenticationError,
      404 => NotFoundError,
      409 => ConflictError,
      422 => UnprocessableEntityError,
      429 => RateLimitError
    }.freeze

    module_function

    # @param status [Integer]
    # @param body [Object] parsed response body
    # @param request_method [Symbol]
    # @param path [String]
    # @return [ApiError]
    def build(status:, body:, request_method:, path:)
      klass =
        STATUS_MAP[status] || (status.to_i >= 500 ? ServerError : ApiError)
      klass.new(
        status: status,
        body: body,
        request_method: request_method,
        path: path
      )
    end
  end
end
