// Main application for Euro AIP Airport Explorer
class AirportExplorerApp {
    constructor() {
        this.initialized = false;
        this.loadingState = false;
    }

    async init() {
        try {
            console.log('Initializing Euro AIP Airport Explorer...');
            
            // Check API health first
            await this.checkAPIHealth();
            
            // Initialize components
            this.initializeComponents();
            
            // Load initial data
            await this.loadInitialData();
            
            // Set up event listeners
            this.setupEventListeners();
            
            this.initialized = true;
            console.log('Application initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize application:', error);
            this.showInitializationError(error);
        }
    }

    async checkAPIHealth() {
        try {
            const health = await api.healthCheck();
            console.log('API Health Check:', health);
            
            if (health.status !== 'healthy') {
                throw new Error('API is not healthy');
            }
            
            return health;
        } catch (error) {
            throw new Error(`API health check failed: ${error.message}`);
        }
    }

    initializeComponents() {
        // Initialize map
        airportMap = new AirportMap('map');
        
        // Initialize filter manager
        filterManager = new FilterManager();
        
        // Initialize chart manager
        chartManager = new ChartManager();
        
        console.log('Components initialized');
    }

    async loadInitialData() {
        try {
            this.showLoadingState();
            
            // Load filter options
            await filterManager.loadAvailableFilters();
            
            // Set default border crossing filter and load airports
            filterManager.setDefaultBorderCrossingFilter();
            
            console.log('Loaded border crossing airports by default');
            
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showError('Failed to load initial data: ' + error.message);
        } finally {
            this.hideLoadingState();
        }
    }

    setupEventListeners() {
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + F to focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                document.getElementById('search-input').focus();
            }
            
            // Escape to clear search
            if (e.key === 'Escape') {
                document.getElementById('search-input').value = '';
                filterManager.handleSearch('');
            }
            
            // Ctrl/Cmd + R to reset zoom
            if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
                e.preventDefault();
                filterManager.resetZoom();
            }
        });

        // Window resize handling
        window.addEventListener('resize', () => {
            if (airportMap && airportMap.map) {
                airportMap.map.invalidateSize();
            }
        });

        // Add some helpful tooltips
        this.addTooltips();
    }

    addTooltips() {
        // Initialize Bootstrap tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    showLoadingState() {
        this.loadingState = true;
        document.getElementById('loading').style.display = 'block';
        
        // Disable filter controls
        const filterControls = [
            'apply-filters',
            'reset-zoom',
            'search-input',
            'country-filter',
            'procedure-filter',
            'approach-filter',
            'has-procedures',
            'has-runways',
            'has-aip-data',
            'has-hard-runway',
            'border-crossing-only'
        ];
        
        filterControls.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.disabled = true;
            }
        });
    }

    hideLoadingState() {
        this.loadingState = false;
        document.getElementById('loading').style.display = 'none';
        
        // Re-enable filter controls
        const filterControls = [
            'apply-filters',
            'reset-zoom',
            'search-input',
            'country-filter',
            'procedure-filter',
            'approach-filter',
            'has-procedures',
            'has-runways',
            'has-aip-data',
            'has-hard-runway',
            'border-crossing-only'
        ];
        
        filterControls.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.disabled = false;
            }
        });
    }

    showError(message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show position-fixed';
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alertDiv.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Auto-remove after 8 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 8000);
    }

    showInitializationError(error) {
        const container = document.querySelector('.container-fluid');
        container.innerHTML = `
            <div class="row mt-5">
                <div class="col-12">
                    <div class="alert alert-danger text-center">
                        <h4><i class="fas fa-exclamation-triangle"></i> Application Initialization Failed</h4>
                        <p class="mb-3">${error.message}</p>
                        <p class="mb-3">Please check that:</p>
                        <ul class="text-start">
                            <li>The FastAPI server is running on port 8000</li>
                            <li>The airports.db file exists and is accessible</li>
                            <li>All required dependencies are installed</li>
                        </ul>
                        <button class="btn btn-primary" onclick="location.reload()">
                            <i class="fas fa-redo"></i> Retry
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    // Utility methods
    getAppInfo() {
        return {
            initialized: this.initialized,
            loadingState: this.loadingState,
            mapMarkers: airportMap ? airportMap.markers.size : 0,
            currentFilters: filterManager ? filterManager.getCurrentFilters() : {},
            timestamp: new Date().toISOString()
        };
    }

    // Export current state
    exportState() {
        return {
            appInfo: this.getAppInfo(),
            filters: filterManager ? filterManager.exportFilters() : {},
            mapBounds: airportMap ? airportMap.map.getBounds() : null,
            timestamp: new Date().toISOString()
        };
    }

    // Import state (for future use)
    importState(state) {
        if (state.filters) {
            // Apply filters
            filterManager.currentFilters = state.filters.filters || {};
            
            // Update UI
            this.updateFilterUI();
            
            // Apply filters
            filterManager.applyFilters();
        }
        
        if (state.mapBounds && airportMap) {
            airportMap.map.fitBounds(state.mapBounds);
        }
    }

    updateFilterUI() {
        const filters = filterManager.currentFilters;
        
        // Update select elements
        if (filters.country) {
            document.getElementById('country-filter').value = filters.country;
        }
        if (filters.procedure_type) {
            document.getElementById('procedure-filter').value = filters.procedure_type;
        }
        if (filters.approach_type) {
            document.getElementById('approach-filter').value = filters.approach_type;
        }
        
        // Update checkboxes
        document.getElementById('has-procedures').checked = filters.has_procedures === true;
        document.getElementById('has-runways').checked = filters.has_runways === true;
        document.getElementById('has-aip-data').checked = filters.has_aip_data === true;
        document.getElementById('border-crossing-only').checked = filters.point_of_entry === true;
    }
}

// Global app instance
let app;

// Initialize application when DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
    app = new AirportExplorerApp();
    await app.init();
});

// Add some global utility functions
window.AirportExplorer = {
    // Get app instance
    getApp: () => app,
    
    // Get API client
    getAPI: () => api,
    
    // Get map instance
    getMap: () => airportMap,
    
    // Get filter manager
    getFilters: () => filterManager,
    
    // Get chart manager
    getCharts: () => chartManager,
    
    // Export current state
    exportState: () => app ? app.exportState() : null,
    
    // Import state
    importState: (state) => app ? app.importState(state) : null,
    
    // Reload application
    reload: () => location.reload(),
    
    // Show app info
    showInfo: () => {
        const info = app ? app.getAppInfo() : null;
        console.log('App Info:', info);
        alert(JSON.stringify(info, null, 2));
    }
};

// Add some helpful console messages
console.log(`
🚁 Euro AIP Airport Explorer
============================

Available global functions:
- AirportExplorer.getApp() - Get app instance
- AirportExplorer.getAPI() - Get API client
- AirportExplorer.getMap() - Get map instance
- AirportExplorer.getFilters() - Get filter manager
- AirportExplorer.getCharts() - Get chart manager
- AirportExplorer.exportState() - Export current state
- AirportExplorer.importState(state) - Import state
- AirportExplorer.reload() - Reload application
- AirportExplorer.showInfo() - Show app info

Keyboard shortcuts:
- Ctrl/Cmd + F - Focus search
- Escape - Clear search
`); 