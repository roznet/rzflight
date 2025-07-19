// Charts functionality for Euro AIP Airport Explorer
class ChartManager {
    constructor() {
        this.charts = {};
        this.initCharts();
    }

    initCharts() {
        // Initialize procedure distribution chart
        this.initProcedureChart();
        
        // Initialize country distribution chart
        this.initCountryChart();
    }

    initProcedureChart() {
        const ctx = document.getElementById('procedure-chart').getContext('2d');
        
        this.charts.procedure = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    backgroundColor: [
                        '#FF6384',
                        '#36A2EB',
                        '#FFCE56',
                        '#4BC0C0',
                        '#9966FF',
                        '#FF9F40',
                        '#FF6384',
                        '#C9CBCF'
                    ],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    initCountryChart() {
        const ctx = document.getElementById('country-chart').getContext('2d');
        
        this.charts.country = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Airports',
                    data: [],
                    backgroundColor: 'rgba(54, 162, 235, 0.8)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Airports: ${context.parsed.y}`;
                            }
                        }
                    }
                }
            }
        });
    }

    async updateProcedureChart() {
        try {
            const data = await api.getProcedureDistribution();
            
            if (data.procedure_types && data.procedure_types.length > 0) {
                const labels = data.procedure_types.map(item => item.type.toUpperCase());
                const values = data.procedure_types.map(item => item.count);
                
                this.charts.procedure.data.labels = labels;
                this.charts.procedure.data.datasets[0].data = values;
                this.charts.procedure.update();
            }
        } catch (error) {
            console.error('Error updating procedure chart:', error);
        }
    }

    async updateCountryChart() {
        try {
            const data = await api.getStatisticsByCountry();
            
            if (data && data.length > 0) {
                // Sort by airport count and take top 10
                const sortedData = data
                    .sort((a, b) => b.total_airports - a.total_airports)
                    .slice(0, 10);
                
                const labels = sortedData.map(item => item.country);
                const values = sortedData.map(item => item.total_airports);
                
                this.charts.country.data.labels = labels;
                this.charts.country.data.datasets[0].data = values;
                this.charts.country.update();
            }
        } catch (error) {
            console.error('Error updating country chart:', error);
        }
    }

    async updateAllCharts() {
        await Promise.all([
            this.updateProcedureChart(),
            this.updateCountryChart()
        ]);
    }

    // Create a custom chart for approach types
    createApproachTypeChart(containerId) {
        const canvas = document.createElement('canvas');
        canvas.id = 'approach-chart';
        document.getElementById(containerId).appendChild(canvas);
        
        const ctx = canvas.getContext('2d');
        
        return new Chart(ctx, {
            type: 'pie',
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    backgroundColor: [
                        '#28a745', // ILS - Green
                        '#007bff', // RNAV - Blue
                        '#17a2b8', // VOR - Cyan
                        '#ffc107', // NDB - Yellow
                        '#6c757d'  // Other - Gray
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'right'
                    },
                    title: {
                        display: true,
                        text: 'Approach Types Distribution'
                    }
                }
            }
        });
    }

    // Create a chart for runway statistics
    createRunwayChart(containerId) {
        const canvas = document.createElement('canvas');
        canvas.id = 'runway-chart';
        document.getElementById(containerId).appendChild(canvas);
        
        const ctx = canvas.getContext('2d');
        
        return new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Runway Length (ft)',
                    data: [],
                    backgroundColor: 'rgba(255, 99, 132, 0.8)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Length (ft)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Length Range'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Runway Length Distribution'
                    }
                }
            }
        });
    }

    // Update approach type chart with data
    updateApproachTypeChart(chart, data) {
        if (data.approach_types && data.approach_types.length > 0) {
            const labels = data.approach_types.map(item => item.type);
            const values = data.approach_types.map(item => item.count);
            
            chart.data.labels = labels;
            chart.data.datasets[0].data = values;
            chart.update();
        }
    }

    // Update runway chart with data
    updateRunwayChart(chart, data) {
        if (data.lengths && data.lengths.distribution) {
            const labels = data.lengths.distribution.map(item => item.range);
            const values = data.lengths.distribution.map(item => item.count);
            
            chart.data.labels = labels;
            chart.data.datasets[0].data = values;
            chart.update();
        }
    }

    // Create a comprehensive statistics dashboard
    async createStatisticsDashboard(containerId) {
        const container = document.getElementById(containerId);
        container.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h6><i class="fas fa-chart-pie"></i> Procedure Types</h6>
                        </div>
                        <div class="card-body">
                            <canvas id="dashboard-procedure-chart" width="400" height="200"></canvas>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h6><i class="fas fa-chart-bar"></i> Countries</h6>
                        </div>
                        <div class="card-body">
                            <canvas id="dashboard-country-chart" width="400" height="200"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row mt-3">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h6><i class="fas fa-plane"></i> Approach Types</h6>
                        </div>
                        <div class="card-body">
                            <canvas id="dashboard-approach-chart" width="400" height="200"></canvas>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h6><i class="fas fa-ruler"></i> Runway Lengths</h6>
                        </div>
                        <div class="card-body">
                            <canvas id="dashboard-runway-chart" width="400" height="200"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Initialize dashboard charts
        await this.initializeDashboardCharts();
    }

    async initializeDashboardCharts() {
        try {
            // Load all statistics data
            const [procedureData, countryData, approachData, runwayData] = await Promise.all([
                api.getProcedureDistribution(),
                api.getStatisticsByCountry(),
                api.getProcedureDistribution(),
                api.getRunwayStatistics()
            ]);

            // Create and update charts
            this.createDashboardProcedureChart(procedureData);
            this.createDashboardCountryChart(countryData);
            this.createDashboardApproachChart(approachData);
            this.createDashboardRunwayChart(runwayData);

        } catch (error) {
            console.error('Error initializing dashboard charts:', error);
        }
    }

    createDashboardProcedureChart(data) {
        const ctx = document.getElementById('dashboard-procedure-chart').getContext('2d');
        
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.procedure_types?.map(item => item.type.toUpperCase()) || [],
                datasets: [{
                    data: data.procedure_types?.map(item => item.count) || [],
                    backgroundColor: [
                        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
                        '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }

    createDashboardCountryChart(data) {
        const ctx = document.getElementById('dashboard-country-chart').getContext('2d');
        
        const topCountries = data
            .sort((a, b) => b.total_airports - a.total_airports)
            .slice(0, 8);
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: topCountries.map(item => item.country),
                datasets: [{
                    label: 'Airports',
                    data: topCountries.map(item => item.total_airports),
                    backgroundColor: 'rgba(54, 162, 235, 0.8)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    createDashboardApproachChart(data) {
        const ctx = document.getElementById('dashboard-approach-chart').getContext('2d');
        
        new Chart(ctx, {
            type: 'pie',
            data: {
                labels: data.approach_types?.map(item => item.type) || [],
                datasets: [{
                    data: data.approach_types?.map(item => item.count) || [],
                    backgroundColor: [
                        '#28a745', '#007bff', '#17a2b8', '#ffc107', '#6c757d'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }

    createDashboardRunwayChart(data) {
        const ctx = document.getElementById('dashboard-runway-chart').getContext('2d');
        
        const distribution = data.lengths?.distribution || [];
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: distribution.map(item => item.range),
                datasets: [{
                    label: 'Runways',
                    data: distribution.map(item => item.count),
                    backgroundColor: 'rgba(255, 99, 132, 0.8)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }
}

// Create global chart manager instance
let chartManager; 