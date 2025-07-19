// Map functionality for Euro AIP Airport Explorer
class AirportMap {
    constructor(containerId) {
        this.containerId = containerId;
        this.map = null;
        this.markers = new Map(); // ICAO -> marker
        this.procedureLines = new Map(); // ICAO -> array of lines
        this.currentAirport = null;
        this.airportLayer = null;
        this.procedureLayer = null;
        this.legendMode = 'airport-type';
        
        // Don't initialize map immediately - let the app handle it
        console.log(`AirportMap constructor called for container: ${containerId}`);
    }

    initMap() {
        // Check if Leaflet is available
        if (typeof L === 'undefined') {
            console.error('Leaflet library not loaded. Please ensure leaflet.js is loaded before map.js');
            return;
        }
        
        // Check if container exists
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`Map container with id '${this.containerId}' not found. DOM may not be ready yet.`);
            return;
        }
        
        try {
            // Initialize Leaflet map centered on Europe
            this.map = L.map(this.containerId).setView([50.0, 10.0], 5);
            
            // Add OpenStreetMap tiles
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(this.map);
            
            // Create airport layer group
            this.airportLayer = L.layerGroup().addTo(this.map);
            
            // Create procedure lines layer group
            this.procedureLayer = L.layerGroup().addTo(this.map);
            
            // Add scale control
            L.control.scale().addTo(this.map);
            
            console.log('Map initialized successfully');
        } catch (error) {
            console.error('Error initializing map:', error);
        }
    }

    clearMarkers() {
        this.airportLayer.clearLayers();
        this.procedureLayer.clearLayers();
        this.markers.clear();
        this.procedureLines.clear();
    }

    addAirport(airport) {
        if (!airport.latitude_deg || !airport.longitude_deg) {
            return; // Skip airports without coordinates
        }

        // Add airport marker based on current legend mode
        if (this.legendMode === 'procedure-precision') {
            this.addAirportWithProcedures(airport);
        } else {
            this.addAirportMarker(airport);
        }
    }

    addAirportMarker(airport) {
        // Determine marker color based on airport characteristics
        let color = '#ffc107'; // Default: yellow (no procedures)
        let radius = 6;
        
        if (airport.point_of_entry) {
            color = '#dc3545'; // Red for border crossing
            radius = 8;
        } else if (airport.has_procedures) {
            color = '#28a745'; // Green for airports with procedures
            radius = 7;
        }

        // Create custom icon
        const icon = L.divIcon({
            className: 'airport-marker',
            html: `<div style="
                width: ${radius * 2}px; 
                height: ${radius * 2}px; 
                background-color: ${color}; 
                border: 2px solid white; 
                border-radius: 50%; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            "></div>`,
            iconSize: [radius * 2, radius * 2],
            iconAnchor: [radius, radius]
        });

        // Create marker
        const marker = L.marker([airport.latitude_deg, airport.longitude_deg], {
            icon: icon
        });

        // Create popup content
        const popupContent = this.createPopupContent(airport);
        marker.bindPopup(popupContent, {
            maxWidth: 300,
            maxHeight: 200
        });

        // Add click event
        marker.on('click', () => {
            this.onAirportClick(airport);
        });

        // Add to map and store reference
        marker.addTo(this.airportLayer);
        this.markers.set(airport.ident, marker);
    }

    async addAirportWithProcedures(airport) {
        // Create transparent marker for airports without procedures
        let color = 'rgba(128, 128, 128, 0.3)';
        let borderColor = 'rgba(128, 128, 128, 0.5)';
        let radius = 6;

        // Create custom icon
        const icon = L.divIcon({
            className: 'airport-marker',
            html: `<div style="
                width: ${radius * 2}px; 
                height: ${radius * 2}px; 
                background-color: ${color}; 
                border: 2px solid ${borderColor}; 
                border-radius: 50%; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            "></div>`,
            iconSize: [radius * 2, radius * 2],
            iconAnchor: [radius, radius]
        });

        // Create marker
        const marker = L.marker([airport.latitude_deg, airport.longitude_deg], {
            icon: icon
        });

        // Create popup content
        const popupContent = this.createPopupContent(airport);
        marker.bindPopup(popupContent, {
            maxWidth: 300,
            maxHeight: 200
        });

        // Add click event
        marker.on('click', () => {
            this.onAirportClick(airport);
        });

        // Add to map and store reference
        marker.addTo(this.airportLayer);
        this.markers.set(airport.ident, marker);

        // Add procedure lines if airport has procedures
        if (airport.has_procedures) {
            await this.addProcedureLines(airport);
        }
    }

    async addProcedureLines(airport) {
        try {
            // Get procedure lines from the new API endpoint
            const procedureData = await api.getAirportProcedureLines(airport.ident);

            const lines = [];
            
            // Process each procedure line
            for (const lineData of procedureData.procedure_lines) {
                // Determine line color based on precision category
                let lineColor = '#ffffff'; // Default: white
                switch (lineData.precision_category) {
                    case 'precision':
                        lineColor = '#ffff00'; // Yellow for ILS
                        break;
                    case 'rnp':
                        lineColor = '#0000ff'; // Blue for RNP/RNAV
                        break;
                    case 'non-precision':
                        lineColor = '#ffffff'; // White for VOR/NDB
                        break;
                }

                // Create the line
                const line = L.polyline([
                    [lineData.start_lat, lineData.start_lon],
                    [lineData.end_lat, lineData.end_lon]
                ], {
                    color: lineColor,
                    weight: 3,
                    opacity: 0.8
                });

                // Add popup to line
                line.bindPopup(`
                    <div style="min-width: 200px;">
                        <h6><strong>${airport.ident} ${lineData.runway_end}</strong></h6>
                        <p><strong>Approach:</strong> ${lineData.procedure_name || 'N/A'}</p>
                        <p><strong>Type:</strong> ${lineData.approach_type}</p>
                        <p><strong>Precision:</strong> ${this.getPrecisionDescription(lineData.approach_type)}</p>
                    </div>
                `);

                line.addTo(this.procedureLayer);
                lines.push(line);
            }

            this.procedureLines.set(airport.ident, lines);

        } catch (error) {
            console.error(`Error adding procedure lines for ${airport.ident}:`, error);
        }
    }



    getPrecisionDescription(approachType) {
        switch (approachType) {
            case 'ILS': return 'Highest (CAT I/II/III)';
            case 'RNP':
            case 'RNAV': return 'High (RNP 0.3-1.0)';
            case 'LOC':
            case 'LDA':
            case 'SDF': return 'Medium (Localizer)';
            case 'VOR':
            case 'NDB': return 'Lower (Non-precision)';
            default: return 'Standard';
        }
    }

    createPopupContent(airport) {
        let content = `
            <div style="min-width: 200px;">
                <h6><strong>${airport.ident}</strong></h6>
                <p style="margin: 5px 0;">${airport.name || 'N/A'}</p>
        `;

        if (airport.municipality) {
            content += `<p style="margin: 2px 0; font-size: 0.9em; color: #666;">
                <i class="fas fa-map-marker-alt"></i> ${airport.municipality}
            </p>`;
        }

        if (airport.iso_country) {
            content += `<p style="margin: 2px 0; font-size: 0.9em; color: #666;">
                <i class="fas fa-flag"></i> ${airport.iso_country}
            </p>`;
        }

        // Add procedure count
        if (airport.procedure_count > 0) {
            content += `<p style="margin: 2px 0; font-size: 0.9em; color: #28a745;">
                <i class="fas fa-route"></i> ${airport.procedure_count} procedures
            </p>`;
        }

        // Add runway count
        if (airport.runway_count > 0) {
            content += `<p style="margin: 2px 0; font-size: 0.9em; color: #007bff;">
                <i class="fas fa-plane"></i> ${airport.runway_count} runways
            </p>`;
        }

        // Add border crossing indicator
        if (airport.point_of_entry) {
            content += `<p style="margin: 2px 0; font-size: 0.9em; color: #dc3545;">
                <i class="fas fa-passport"></i> Border Crossing
            </p>`;
        }

        content += '</div>';
        return content;
    }

    async onAirportClick(airport) {
        try {
            // Show loading state
            this.showAirportDetailsLoading();
            
            // Get detailed airport information
            const [airportDetail, procedures, runways, aipEntries] = await Promise.all([
                api.getAirportDetail(airport.ident),
                api.getAirportProcedures(airport.ident),
                api.getAirportRunways(airport.ident),
                api.getAirportAIPEntries(airport.ident)
            ]);

            // Display airport details
            this.displayAirportDetails(airportDetail, procedures, runways, aipEntries);
            
        } catch (error) {
            console.error('Error loading airport details:', error);
            this.showAirportDetailsError(error);
        }
    }

    showAirportDetailsLoading() {
        const detailsContainer = document.getElementById('airport-details');
        const infoContainer = document.getElementById('airport-info');
        
        detailsContainer.style.display = 'block';
        document.getElementById('no-selection').style.display = 'none';
        
        infoContainer.innerHTML = `
            <div class="text-center">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2">Loading airport details...</p>
            </div>
        `;
    }

    showAirportDetailsError(error) {
        const infoContainer = document.getElementById('airport-info');
        infoContainer.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle"></i>
                Error loading airport details: ${error.message}
            </div>
        `;
    }

    displayAirportDetails(airport, procedures, runways, aipEntries) {
        const infoContainer = document.getElementById('airport-info');
        const detailsContainer = document.getElementById('airport-details');
        const aipContainer = document.getElementById('aip-data');
        const noSelectionContainer = document.getElementById('no-selection');
        const noAipDataContainer = document.getElementById('no-aip-data');
        
        if (!airport) {
            detailsContainer.style.display = 'none';
            aipContainer.style.display = 'none';
            noSelectionContainer.style.display = 'block';
            noAipDataContainer.style.display = 'block';
            return;
        }
        
        detailsContainer.style.display = 'block';
        noSelectionContainer.style.display = 'none';
        
        // Display airport details (left panel)
        let html = `
            <div class="airport-detail-section">
                <h6><i class="fas fa-info-circle"></i> Basic Information</h6>
                <table class="table table-sm">
                    <tr><td><strong>ICAO:</strong></td><td>${airport.ident}</td></tr>
                    <tr><td><strong>Name:</strong></td><td>${airport.name || 'N/A'}</td></tr>
                    <tr><td><strong>Type:</strong></td><td>${airport.type || 'N/A'}</td></tr>
                    <tr><td><strong>Country:</strong></td><td>${airport.iso_country || 'N/A'}</td></tr>
                    <tr><td><strong>Region:</strong></td><td>${airport.iso_region || 'N/A'}</td></tr>
                    <tr><td><strong>Municipality:</strong></td><td>${airport.municipality || 'N/A'}</td></tr>
                    <tr><td><strong>Coordinates:</strong></td><td>${airport.latitude_deg?.toFixed(4)}, ${airport.longitude_deg?.toFixed(4)}</td></tr>
                    <tr><td><strong>Elevation:</strong></td><td>${airport.elevation_ft || 'N/A'} ft</td></tr>
                </table>
            </div>
        `;

        // Add links section if available
        const links = [];
        if (airport.home_link) {
            links.push(`<a href="${airport.home_link}" target="_blank" class="btn btn-outline-primary btn-sm me-2">
                <i class="fas fa-home"></i> Home Page
            </a>`);
        }
        if (airport.wikipedia_link) {
            links.push(`<a href="${airport.wikipedia_link}" target="_blank" class="btn btn-outline-info btn-sm me-2">
                <i class="fab fa-wikipedia-w"></i> Wikipedia
            </a>`);
        }
        
        // Always add EuroGA link since we have the ICAO code
        links.push(`<a href="https://airports.euroga.org/search.php?icao=${airport.ident}" target="_blank" class="btn btn-outline-success btn-sm me-2">
            <i class="fas fa-plane"></i> EuroGA
        </a>`);
        
        if (links.length > 0) {
            html += `
                <div class="airport-detail-section">
                    <h6><i class="fas fa-link"></i> Links</h6>
                    <div class="d-flex flex-wrap gap-2">
                        ${links.join('')}
                    </div>
                </div>
            `;
        }

        // Add runways section
        if (runways && runways.length > 0) {
            html += `
                <div class="airport-detail-section">
                    <h6><i class="fas fa-plane"></i> Runways (${runways.length})</h6>
            `;
            
            runways.forEach(runway => {
                html += `
                    <div class="runway-info">
                        <strong>${runway.le_ident}/${runway.he_ident}</strong><br>
                        Length: ${runway.length_ft || 'N/A'} ft<br>
                        Width: ${runway.width_ft || 'N/A'} ft<br>
                        Surface: ${runway.surface || 'N/A'}<br>
                        ${runway.lighted ? 'Lighted' : 'Not lighted'}
                    </div>
                `;
            });
            
            html += '</div>';
        }

        // Add procedures section
        if (procedures && procedures.length > 0) {
            html += `
                <div class="airport-detail-section">
                    <h6><i class="fas fa-route"></i> Procedures (${procedures.length})</h6>
            `;
            
            // Group procedures by type
            const proceduresByType = {};
            procedures.forEach(proc => {
                const type = proc.procedure_type || 'Unknown';
                if (!proceduresByType[type]) {
                    proceduresByType[type] = [];
                }
                proceduresByType[type].push(proc);
            });
            
            Object.entries(proceduresByType).forEach(([type, procs]) => {
                html += `<h6 class="mt-2">${type.charAt(0).toUpperCase() + type.slice(1)} (${procs.length})</h6>`;
                procs.forEach(proc => {
                    const badgeClass = this.getProcedureBadgeClass(proc.procedure_type, proc.approach_type);
                    html += `<span class="badge ${badgeClass} procedure-badge">${proc.name}</span>`;
                });
            });
            
            html += '</div>';
        }

        // Add sources section
        if (airport.sources && airport.sources.length > 0) {
            html += `
                <div class="airport-detail-section">
                    <h6><i class="fas fa-database"></i> Data Sources</h6>
                    ${airport.sources.map(source => `<span class="badge bg-secondary me-1">${source}</span>`).join('')}
                </div>
            `;
        }

        infoContainer.innerHTML = html;
        
        // Display AIP data (right panel)
        this.displayAIPData(aipEntries);
    }

    displayAIPData(aipEntries) {
        const aipContainer = document.getElementById('aip-data');
        const aipContentContainer = document.getElementById('aip-data-content');
        const noAipDataContainer = document.getElementById('no-aip-data');
        
        if (!aipEntries || aipEntries.length === 0) {
            aipContainer.style.display = 'none';
            noAipDataContainer.style.display = 'block';
            return;
        }
        
        aipContainer.style.display = 'block';
        noAipDataContainer.style.display = 'none';

        // Group by standardized field section
        const entriesBySection = {};
        aipEntries.forEach(entry => {
            // Extract section from std_field_id (e.g., 201 -> admin, 301 -> operational, etc.)
            let section = 'Other';
            if (entry.std_field_id) {
                const sectionId = Math.floor(entry.std_field_id / 100) * 100;
                switch (sectionId) {
                    case 200: section = 'Admin'; break;
                    case 300: section = 'Operational'; break;
                    case 400: section = 'Handling'; break;
                    case 500: section = 'Passenger'; break;
                    default: section = 'Other'; break;
                }
            } else {
                section = entry.section || 'Other';
            }
            
            if (!entriesBySection[section]) {
                entriesBySection[section] = [];
            }
            entriesBySection[section].push(entry);
        });

        let html = '';
        Object.entries(entriesBySection).forEach(([section, entries]) => {
            const sectionId = `aip-section-${section.toLowerCase()}`;
            html += `
                <div class="aip-section" data-section="${section}">
                    <div class="aip-section-header" onclick="airportMap.toggleAIPSection('${sectionId}')">
                        <span>
                            <i class="fas fa-chevron-right aip-section-toggle" id="toggle-${sectionId}"></i>
                            ${section} (${entries.length})
                        </span>
                    </div>
                    <div class="aip-section-content" id="${sectionId}">
            `;
            
            entries.forEach(entry => {
                const fieldName = entry.std_field || entry.field;
                const entryId = `aip-entry-${entry.std_field_id || entry.field}`;
                html += `
                    <div class="aip-entry" id="${entryId}" data-field="${fieldName}" data-value="${entry.value}">
                        <strong>${fieldName}:</strong> ${entry.value}
                        ${entry.alt_value ? `<br><em>${entry.alt_value}</em>` : ''}
                    </div>
                `;
            });
            
            html += `
                    </div>
                </div>
            `;
        });

        aipContentContainer.innerHTML = html;
        
        // Initialize AIP filter
        this.initializeAIPFilter();
    }

    toggleAIPSection(sectionId) {
        const content = document.getElementById(sectionId);
        const toggle = document.getElementById(`toggle-${sectionId}`);
        const isExpanded = content.classList.contains('expanded');
        
        if (isExpanded) {
            content.classList.remove('expanded');
            toggle.classList.remove('expanded');
        } else {
            content.classList.add('expanded');
            toggle.classList.add('expanded');
        }
        
        // Remember state
        this.saveAIPSectionState(sectionId, !isExpanded);
    }

    saveAIPSectionState(sectionId, isExpanded) {
        const states = JSON.parse(localStorage.getItem('aipSectionStates') || '{}');
        states[sectionId] = isExpanded;
        localStorage.setItem('aipSectionStates', JSON.stringify(states));
    }

    loadAIPSectionStates() {
        const states = JSON.parse(localStorage.getItem('aipSectionStates') || '{}');
        Object.entries(states).forEach(([sectionId, isExpanded]) => {
            const content = document.getElementById(sectionId);
            const toggle = document.getElementById(`toggle-${sectionId}`);
            if (content && toggle) {
                if (isExpanded) {
                    content.classList.add('expanded');
                    toggle.classList.add('expanded');
                } else {
                    content.classList.remove('expanded');
                    toggle.classList.remove('expanded');
                }
            }
        });
    }

    initializeAIPFilter() {
        const filterInput = document.getElementById('aip-filter-input');
        const clearButton = document.getElementById('aip-filter-clear');
        if (!filterInput) return;

        // Remove existing event listeners
        filterInput.removeEventListener('input', this.handleAIPFilter);
        if (clearButton) {
            clearButton.removeEventListener('click', this.clearAIPFilter);
        }
        
        // Add new event listeners
        this.handleAIPFilter = this.handleAIPFilter.bind(this);
        this.clearAIPFilter = this.clearAIPFilter.bind(this);
        filterInput.addEventListener('input', this.handleAIPFilter);
        if (clearButton) {
            clearButton.addEventListener('click', this.clearAIPFilter);
        }
        
        // Load saved section states
        this.loadAIPSectionStates();
    }

    clearAIPFilter() {
        const filterInput = document.getElementById('aip-filter-input');
        if (filterInput) {
            filterInput.value = '';
            this.handleAIPFilter({ target: { value: '' } });
        }
    }

    handleAIPFilter(event) {
        const filterText = event.target.value.toLowerCase();
        const entries = document.querySelectorAll('.aip-entry');
        
        entries.forEach(entry => {
            const fieldName = entry.dataset.field || '';
            const value = entry.dataset.value || '';
            const altValue = entry.querySelector('em')?.textContent || '';
            
            const matches = fieldName.toLowerCase().includes(filterText) || 
                           value.toLowerCase().includes(filterText) ||
                           altValue.toLowerCase().includes(filterText);
            
            if (matches) {
                entry.classList.remove('hidden');
                // Highlight matching text if filter is not empty
                if (filterText) {
                    entry.classList.add('highlight');
                } else {
                    entry.classList.remove('highlight');
                }
                
                // Show parent section if entry matches
                const section = entry.closest('.aip-section');
                if (section) {
                    const content = section.querySelector('.aip-section-content');
                    const toggle = section.querySelector('.aip-section-toggle');
                    content.classList.add('expanded');
                    toggle.classList.add('expanded');
                }
            } else {
                entry.classList.add('hidden');
                entry.classList.remove('highlight');
            }
        });
        
        // Hide sections that have no visible entries
        const sections = document.querySelectorAll('.aip-section');
        sections.forEach(section => {
            const visibleEntries = section.querySelectorAll('.aip-entry:not(.hidden)');
            if (visibleEntries.length === 0) {
                section.style.display = 'none';
            } else {
                section.style.display = 'block';
            }
        });
    }

    getProcedureBadgeClass(procedureType, approachType) {
        if (procedureType === 'approach') {
            switch (approachType?.toUpperCase()) {
                case 'ILS': return 'bg-success';
                case 'RNAV': return 'bg-primary';
                case 'VOR': return 'bg-info';
                case 'NDB': return 'bg-warning';
                default: return 'bg-secondary';
            }
        } else if (procedureType === 'departure') {
            return 'bg-danger';
        } else if (procedureType === 'arrival') {
            return 'bg-warning';
        }
        return 'bg-secondary';
    }

    fitBounds() {
        if (this.markers.size === 0) return;
        
        const group = new L.featureGroup(Array.from(this.markers.values()));
        this.map.fitBounds(group.getBounds().pad(0.1));
    }

    setView(lat, lng, zoom) {
        if (this.map) {
            this.map.setView([lat, lng], zoom);
        }
    }

    isInitialized() {
        return this.map !== null && typeof this.map !== 'undefined';
    }

    // Filter markers based on criteria
    filterMarkers(filters) {
        this.markers.forEach((marker, icao) => {
            // This will be implemented when we have the full airport data
            // For now, just show all markers
            marker.addTo(this.airportLayer);
        });
    }

    setLegendMode(mode) {
        this.legendMode = mode;
        this.updateLegend();
    }

    updateLegend() {
        const legendContent = document.getElementById('legend-content');
        if (!legendContent) return;

        let html = '';
        
        switch (this.legendMode) {
            case 'airport-type':
                html = `
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #28a745;"></div>
                        <span>Airport with Procedures</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #ffc107;"></div>
                        <span>Airport without Procedures</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #dc3545;"></div>
                        <span>Border Crossing</span>
                    </div>
                `;
                break;
                
            case 'procedure-precision':
                html = `
                    <div class="legend-item">
                        <div class="legend-line" style="background-color: #ffff00;"></div>
                        <span>ILS (Precision)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-line" style="background-color: #0000ff;"></div>
                        <span>RNP/RNAV (RNP)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-line" style="background-color: #ffffff;"></div>
                        <span>VOR/NDB (Non-Precision)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color legend-transparent"></div>
                        <span>Airport without Procedures</span>
                    </div>
                `;
                break;
                
            case 'runway-length':
                html = `
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #28a745;"></div>
                        <span>Long Runway (>8000ft)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #ffc107;"></div>
                        <span>Medium Runway (4000-8000ft)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #dc3545;"></div>
                        <span>Short Runway (<4000ft)</span>
                    </div>
                `;
                break;
                
            case 'country':
                html = `
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #007bff;"></div>
                        <span>France (LF)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #dc3545;"></div>
                        <span>United Kingdom (EG)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #28a745;"></div>
                        <span>Germany (ED)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #ffc107;"></div>
                        <span>Other Countries</span>
                    </div>
                `;
                break;
        }
        
        legendContent.innerHTML = html;
    }
}

// Create global map instance
let airportMap; 