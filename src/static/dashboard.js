const totalRequestsElement = document.getElementById(
    "total-requests"
);

const successfulRequestsElement = document.getElementById(
    "successful-requests"
);

const failedRequestsElement = document.getElementById(
    "failed-requests"
);

const totalTokensElement = document.getElementById(
    "total-tokens"
);

const estimatedCostElement = document.getElementById(
    "estimated-cost"
);

const averageLatencyElement = document.getElementById(
    "average-latency"
);

const providerTableBody = document.getElementById(
    "provider-table-body"
);

const dashboardStatus = document.getElementById(
    "dashboard-status"
);

const refreshButton = document.getElementById(
    "refresh-button"
);


function formatNumber(value) {
    return Number(value).toLocaleString();
}

function formatCost(value) {
    return `$${Number(value).toFixed(8)}`;
}


function renderSummary(data) {
    totalRequestsElement.textContent = formatNumber(
        data.total_requests
    );

    successfulRequestsElement.textContent = formatNumber(
        data.successful_requests
    );

    failedRequestsElement.textContent = formatNumber(
        data.failed_requests
    );

    totalTokensElement.textContent = formatNumber(
        data.total_tokens
    );

    estimatedCostElement.textContent = formatCost(
        data.estimated_cost_usd
    );

    averageLatencyElement.textContent = (
        `${data.average_latency_ms} ms`
    );
}


function renderProviders(providers) {
    providerTableBody.innerHTML = "";

    if (providers.length === 0) {
        const row = document.createElement("tr");

        row.innerHTML = `
            <td colspan="7">
                No AI request metrics recorded yet.
            </td>
        `;

        providerTableBody.appendChild(row);

        return;
    }

    for (const provider of providers) {
        const row = document.createElement("tr");

        row.innerHTML = `
            <td>${provider.provider}</td>
            <td>${formatNumber(provider.requests)}</td>
            <td>${formatNumber(provider.successful_requests)}</td>
            <td>${formatNumber(provider.failed_requests)}</td>
            <td>${formatNumber(provider.total_tokens)}</td>
            <td>${formatCost(provider.estimated_cost_usd)}</td>
            <td>${provider.average_latency_ms} ms</td>
        `;

        providerTableBody.appendChild(row);
    }
}


async function loadDashboard() {
    dashboardStatus.classList.remove("error");
    dashboardStatus.textContent = "Loading metrics...";

    refreshButton.disabled = true;

    try {
        const response = await fetch("/stats");

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const data = await response.json();

        renderSummary(data);
        renderProviders(data.providers);

        dashboardStatus.textContent = (
            `Updated at ${new Date().toLocaleTimeString()}`
        );

    } catch (error) {
        console.error(
            "Failed to load dashboard metrics:",
            error
        );

        dashboardStatus.classList.add("error");

        dashboardStatus.textContent = (
            "Unable to load AI metrics."
        );

    } finally {
        refreshButton.disabled = false;
    }
}


refreshButton.addEventListener(
    "click",
    loadDashboard
);


loadDashboard();
