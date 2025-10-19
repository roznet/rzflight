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
        console.log('Initializing components...');
        
        // Initialize map
        airportMap = new AirportMap('map');
        console.log('AirportMap created:', airportMap);
        
        // Initialize the map after creation
        if (airportMap) {
            airportMap.initMap();
            console.log('Map initialization called');
            
            // Check if map was initialized successfully
            setTimeout(() => {
                if (airportMap.isInitialized()) {
                    console.log('Map initialized successfully');
                } else {
                    console.warn('Map may not have initialized properly');
                }
            }, 100);
        }
        
        // Initialize filter manager
        filterManager = new FilterManager();
        console.log('FilterManager created:', filterManager);
        
        // Initialize chart manager
        chartManager = new ChartManager();
        console.log('ChartManager created:', chartManager);
        
        // Initialize charts after creation
        if (chartManager) {
            chartManager.initCharts();
            console.log('Charts initialization called');
        }
        
        // Initialize legend
        if (airportMap) {
            airportMap.updateLegend();
        }
        
        console.log('Components initialized');
    }

    async loadInitialData() {
        try {
            this.showLoadingState();
            
            // Load filter options
            await filterManager.loadAvailableFilters();
            
            // Parse and apply URL parameters
            await this.applyURLParameters();
            
            // If no URL parameters were applied, set default border crossing filter
            if (!this.hasURLParameters()) {
                filterManager.setDefaultBorderCrossingFilter();
                console.log('Loaded border crossing airports by default');
            }
            
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
        
        // Set up share button
        this.setupShareButton();
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
            'max-airports-filter',
            'legend-mode-filter',
            'has-procedures',
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
            'max-airports-filter',
            'legend-mode-filter',
            'has-procedures',
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

    // URL Parameter functionality
    hasURLParameters() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.toString().length > 0;
    }

    async applyURLParameters() {
        const urlParams = new URLSearchParams(window.location.search);
        console.log('Applying URL parameters:', urlParams.toString());
        
        let hasAppliedParams = false;
        let appliedParams = [];
        
        try {
            // Apply country filter
            if (urlParams.has('country')) {
                const country = urlParams.get('country');
                const countryElement = document.getElementById('country-filter');
                if (countryElement) {
                    countryElement.value = country;
                    hasAppliedParams = true;
                    appliedParams.push(`country=${country}`);
                }
            }
            
            // Apply boolean filters
            const booleanFilters = [
                { param: 'has_procedures', id: 'has-procedures' },
                { param: 'has_aip_data', id: 'has-aip-data' },
                { param: 'has_hard_runway', id: 'has-hard-runway' },
                { param: 'border_crossing_only', id: 'border-crossing-only' }
            ];
            
            for (const filter of booleanFilters) {
                if (urlParams.has(filter.param)) {
                    const value = urlParams.get(filter.param).toLowerCase();
                    const isChecked = value === 'true' || value === '1' || value === 'yes';
                    const element = document.getElementById(filter.id);
                    if (element) {
                        element.checked = isChecked;
                        hasAppliedParams = true;
                        appliedParams.push(`${filter.param}=${isChecked}`);
                    }
                }
            }
            
            // Apply search/route
            if (urlParams.has('search')) {
                const search = decodeURIComponent(urlParams.get('search'));
                const searchElement = document.getElementById('search-input');
                if (searchElement) {
                    searchElement.value = search;
                    hasAppliedParams = true;
                }
            }
            
            // Apply route distance
            if (urlParams.has('route_distance')) {
                const distance = urlParams.get('route_distance');
                const distanceElement = document.getElementById('route-distance');
                if (distanceElement) {
                    distanceElement.value = distance;
                    hasAppliedParams = true;
                }
            }
            
            // Apply max airports
            if (urlParams.has('max_airports')) {
                const maxAirports = urlParams.get('max_airports');
                const maxAirportsElement = document.getElementById('max-airports-filter');
                if (maxAirportsElement) {
                    maxAirportsElement.value = maxAirports;
                    hasAppliedParams = true;
                }
            }
            
            // Apply legend mode
            if (urlParams.has('legend')) {
                const legendMode = urlParams.get('legend');
                const legendElement = document.getElementById('legend-mode-filter');
                if (legendElement) {
                    legendElement.value = legendMode;
                    if (airportMap) {
                        airportMap.legendMode = legendMode;
                        airportMap.updateLegend();
                    }
                    hasAppliedParams = true;
                }
            }
            
            // Apply map settings
            if (urlParams.has('center') && urlParams.has('zoom')) {
                const centerParts = urlParams.get('center').split(',');
                if (centerParts.length === 2) {
                    const lat = parseFloat(centerParts[0]);
                    const lng = parseFloat(centerParts[1]);
                    const zoom = parseInt(urlParams.get('zoom'));
                    
                    if (!isNaN(lat) && !isNaN(lng) && !isNaN(zoom)) {
                        if (airportMap && airportMap.map) {
                            airportMap.map.setView([lat, lng], zoom);
                        }
                        hasAppliedParams = true;
                    }
                }
            }
            
            // If we applied parameters, trigger filter application
            if (hasAppliedParams && filterManager) {
                // Apply filters with URL parameters
                await filterManager.applyFiltersFromURL();
                
                // Apply search if present
                const searchValue = document.getElementById('search-input').value;
                if (searchValue) {
                    await filterManager.handleSearch(searchValue);
                }
                
                console.log('Applied URL parameters successfully');
                console.log('Applied parameters:', appliedParams.join(', '));
            }
            
        } catch (error) {
            console.error('Error applying URL parameters:', error);
            this.showError('Error applying URL configuration: ' + error.message);
        }
    }

    setupShareButton() {
        const shareButton = document.getElementById('share-button');
        if (shareButton) {
            shareButton.addEventListener('click', async () => {
                await this.copyCurrentURL();
            });
        }
    }

    async copyCurrentURL() {
        try {
            const currentURL = window.location.href;
            await navigator.clipboard.writeText(currentURL);
            this.showNotification('URL copied to clipboard!', 'success');
        } catch (err) {
            // Fallback for older browsers
            try {
                const textArea = document.createElement('textarea');
                textArea.value = window.location.href;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                this.showNotification('URL copied to clipboard!', 'success');
            } catch (fallbackErr) {
                console.error('Failed to copy URL:', fallbackErr);
                this.showNotification('Failed to copy URL', 'error');
            }
        }
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'} alert-dismissible fade show`;
        notification.style.position = 'fixed';
        notification.style.top = '20px';
        notification.style.right = '20px';
        notification.style.zIndex = '9999';
        notification.style.minWidth = '300px';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
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
        if (filters.max_airports) {
            document.getElementById('max-airports-filter').value = filters.max_airports;
        }
        
        // Update checkboxes
        document.getElementById('has-procedures').checked = filters.has_procedures === true;
        document.getElementById('has-aip-data').checked = filters.has_aip_data === true;
        document.getElementById('has-hard-runway').checked = filters.has_hard_runway === true;
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