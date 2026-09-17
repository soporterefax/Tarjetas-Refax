const REFAX_LOCAL = ["localhost", "127.0.0.1"].includes(window.location.hostname);
window.REFAX_CONFIG = {
  API_URL: REFAX_LOCAL
    ? "http://127.0.0.1:5000"
    : "https://tarjetas-refax-api-jv-ama0ftf0bbeqg2ec.centralus-01.azurewebsites.net"
};
