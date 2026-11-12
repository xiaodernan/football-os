package os.football.edge;

import java.net.InetAddress;
import java.net.UnknownHostException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import org.springframework.http.HttpHeaders;
import org.springframework.web.server.ServerWebExchange;

/**
 * The identity a request is counted against, at the edge and in the core — one rule, two languages.
 *
 * <p>The Python core's limiter ({@code app/core/rate_policy.py}) and this gateway must agree on who is
 * asking, or a caller gets two different budgets depending on which tier refused it: the edge counting
 * a whole office behind one NAT as one caller while the core counts each account, or the reverse. The
 * rule is therefore stated once here in the same three branches:
 *
 * <ol>
 *   <li>a presented credential wins — {@code acct:<sha256 prefix>}, never the token itself, because the
 *       key is written into a shared store an operator can read;
 *   <li>a forwarded address is believed only when the peer is one of this deployment's trusted proxies,
 *       and then the <em>left-most</em> entry is the client (each proxy appends, so the right-most is
 *       the proxy that spoke to us);
 *   <li>otherwise the socket's own peer address.
 * </ol>
 *
 * <p>A header anyone can type must never mint a new identity: trusting {@code X-Forwarded-For} from an
 * untrusted peer turns a rate limit into a suggestion, because the caller can present a fresh address
 * on every request.
 */
public final class CallerKey {

    private CallerKey() {
    }

    /** The identity, prefixed by how it was established. */
    public static String of(ServerWebExchange exchange, List<String> trustedProxies) {
        String authorization = exchange.getRequest().getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
        if (authorization != null && !authorization.isBlank()) {
            return "acct:" + digest(authorization.trim());
        }
        String peer = peer(exchange);
        String forwarded = exchange.getRequest().getHeaders().getFirst("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank() && isTrusted(peer, trustedProxies)) {
            String first = forwarded.split(",")[0].trim();
            if (!first.isEmpty()) {
                return "fwd:" + first;
            }
        }
        return "ip:" + (peer.isEmpty() ? "unknown" : peer);
    }

    /** The socket's peer, or the empty string when the exchange has none (a test transport). */
    public static String peer(ServerWebExchange exchange) {
        if (exchange.getRequest().getRemoteAddress() == null
                || exchange.getRequest().getRemoteAddress().getAddress() == null) {
            return "";
        }
        return exchange.getRequest().getRemoteAddress().getAddress().getHostAddress();
    }

    /** Whether an address falls inside one of the configured CIDR blocks. */
    public static boolean isTrusted(String peer, List<String> trustedProxies) {
        if (peer == null || peer.isEmpty() || trustedProxies == null) {
            return false;
        }
        InetAddress address;
        try {
            address = InetAddress.getByName(peer);
        } catch (UnknownHostException notAnAddress) {
            return false;
        }
        for (String entry : trustedProxies) {
            String cidr = entry == null ? "" : entry.trim();
            if (cidr.isEmpty()) {
                continue;
            }
            String host = cidr;
            int prefix = -1;
            int slash = cidr.indexOf('/');
            if (slash >= 0) {
                host = cidr.substring(0, slash);
                try {
                    prefix = Integer.parseInt(cidr.substring(slash + 1));
                } catch (NumberFormatException malformed) {
                    continue;
                }
            }
            InetAddress network;
            try {
                network = InetAddress.getByName(host);
            } catch (UnknownHostException notAnAddress) {
                continue;
            }
            byte[] candidate = address.getAddress();
            byte[] base = network.getAddress();
            if (candidate.length != base.length) {
                continue;
            }
            int bits = prefix < 0 ? base.length * 8 : prefix;
            if (bits < 0 || bits > base.length * 8) {
                continue;
            }
            if (samePrefix(candidate, base, bits)) {
                return true;
            }
        }
        return false;
    }

    private static boolean samePrefix(byte[] candidate, byte[] base, int bits) {
        int full = bits / 8;
        for (int index = 0; index < full; index++) {
            if (candidate[index] != base[index]) {
                return false;
            }
        }
        int remaining = bits % 8;
        if (remaining == 0) {
            return true;
        }
        int mask = 0xFF << (8 - remaining);
        return (candidate[full] & mask) == (base[full] & mask);
    }

    /** A stable name for a credential that is not the credential. */
    public static String digest(String credential) {
        try {
            MessageDigest sha = MessageDigest.getInstance("SHA-256");
            byte[] hashed = sha.digest(credential.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hashed).substring(0, 32);
        } catch (NoSuchAlgorithmException impossible) {
            // Every JRE is required to provide SHA-256; a missing one is not a state to degrade into.
            throw new IllegalStateException("SHA-256 is unavailable", impossible);
        }
    }
}
