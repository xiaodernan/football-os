package os.football.jobsobserver.web;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;
import os.football.jobsobserver.observer.JobsStreamObserver;
import os.football.jobsobserver.observer.ObserverHealth;
import os.football.jobsobserver.observer.StreamLedger;

import java.time.Instant;
import java.util.Map;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * The terminal door's shape contract: one route, always 200, always the declared keys. The
 * observer is mocked at its boundary — the MVC slice never touches Redis, so this test still
 * runs on a laptop without a store.
 */
@WebMvcTest(JobsObserverController.class)
class JobsObserverControllerTest {

    @Autowired
    MockMvc mvc;

    @MockBean
    JobsStreamObserver observer;

    @MockBean
    ObserverHealth health;

    @Test
    void the_door_answers_the_declared_shape() throws Exception {
        var ledger = new StreamLedger("football_os:jobs", "football_os:jobs:observers", "jobs-observer-test");
        ledger.observe("video", "9-1", Instant.parse("2026-11-16T00:00:00Z"));

        when(observer.ledger()).thenReturn(ledger);
        when(observer.streamLength()).thenReturn(41L);
        when(observer.pendingCount()).thenReturn(3L);
        when(observer.streamExists()).thenReturn(true);
        when(health.toPayload()).thenReturn(Map.of(
                "state", ObserverHealth.State.CONNECTED.name(),
                "connected", true,
                "total_polls", 12L,
                "total_failures", 0L));

        mvc.perform(get("/jobs/observer"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total_observed").value(1))
                .andExpect(jsonPath("$.per_type.video").value(1))
                .andExpect(jsonPath("$.stream_length").value(41))
                .andExpect(jsonPath("$.pending_messages").value(3))
                .andExpect(jsonPath("$.stream_exists").value(true))
                .andExpect(jsonPath("$.connection.state").value("CONNECTED"));
    }

    @Test
    void an_empty_ledger_still_answers_200() throws Exception {
        var ledger = new StreamLedger("football_os:jobs", "football_os:jobs:observers", "jobs-observer-test");
        when(observer.ledger()).thenReturn(ledger);
        when(observer.streamLength()).thenReturn(null);
        when(observer.pendingCount()).thenReturn(null);
        when(observer.streamExists()).thenReturn(false);
        when(health.toPayload()).thenReturn(Map.of(
                "state", ObserverHealth.State.NONE_YET.name(),
                "connected", false,
                "total_polls", 0L,
                "total_failures", 0L));

        mvc.perform(get("/jobs/observer"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total_observed").value(0))
                .andExpect(jsonPath("$.recent_record_ids").isArray())
                .andExpect(jsonPath("$.stream_exists").value(false))
                .andExpect(jsonPath("$.connection.state").value("NONE_YET"));
    }
}
