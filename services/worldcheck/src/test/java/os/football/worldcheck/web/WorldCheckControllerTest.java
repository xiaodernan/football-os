package os.football.worldcheck.web;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.any;

import os.football.worldcheck.world.WorldCheckOrchestrator;
import os.football.worldcheck.world.WorldCheckResult;
import os.football.worldcheck.world.WorldCheckInvariants;
import os.football.worldcheck.world.WorldStatus;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.time.Instant;
import java.util.List;
import java.util.Map;

@WebMvcTest(WorldCheckController.class)
class WorldCheckControllerTest {

    @Autowired
    MockMvc mvc;

    @MockBean
    WorldCheckOrchestrator orchestrator;

    private WorldCheckResult fixtureResult() {
        var invariants = List.of(new WorldCheckInvariants.Named("competitions", 10, 12, true));
        return new WorldCheckResult(
                Instant.parse("2026-11-15T00:00:00Z"),
                "world-status-v1",
                new WorldCheckResult.PlayerFace(12, 40, 500, 280, 8400, 824),
                true,
                invariants,
                List.of(),
                120L,
                "http://localhost:8100",
                null);
    }

    @Test
    void the_live_check_door_reports_invariants_and_face() throws Exception {
        when(orchestrator.now()).thenReturn(fixtureResult());

        MvcResult result = mvc.perform(get("/world/check"))
                .andExpect(status().isOk())
                .andReturn();

        @SuppressWarnings("unchecked")
        Map<String, Object> body = new ObjectMapper().readValue(
                result.getResponse().getContentAsByteArray(), Map.class);
        assertThat(body.get("world_aligned")).isEqualTo(true);
        assertThat(body.get("version")).isEqualTo("world-status-v1");
        assertThat(body.get("elapsed_ms")).isEqualTo(120);
        assertThat((List<?>) body.get("invariants")).hasSize(1);
    }

    @Test
    void the_cached_door_answers_precondition_required_before_any_probe() throws Exception {
        when(orchestrator.lastResult()).thenReturn(null);

        MvcResult result = mvc.perform(get("/world/check/cached"))
                .andExpect(status().isPreconditionRequired())
                .andReturn();

        @SuppressWarnings("unchecked")
        Map<String, Object> body = new ObjectMapper().readValue(
                result.getResponse().getContentAsByteArray(), Map.class);
        assertThat(body.get("error")).isEqualTo("worldcheck-not-yet");
    }

    @Test
    void the_cached_door_returns_most_recent_probe_when_present() throws Exception {
        when(orchestrator.lastResult()).thenReturn(fixtureResult());

        MvcResult result = mvc.perform(get("/world/check/cached"))
                .andExpect(status().isOk())
                .andReturn();

        @SuppressWarnings("unchecked")
        Map<String, Object> body = new ObjectMapper().readValue(
                result.getResponse().getContentAsByteArray(), Map.class);
        assertThat(body.get("world_aligned")).isEqualTo(true);
    }
}
