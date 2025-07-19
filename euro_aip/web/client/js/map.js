// Map functionality for Euro AIP Airport Explorer
class AirportMap {
    constructor(containerId) {
        this.containerId = containerId;
        this.map = null;
        this.markers = new Map(); // ICAO -> marker
        this.currentAirport = null;
        this.airportLayer = null;
        
        this.initMap();
    }

    initMap() {
        // Initialize Leaflet map centered on France
        this.map = L.map(this.containerId).setView([46.5, 2.0], 6);
        
        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(this.map);
        
        // Create airport layer group
        this.airportLayer = L.layerGroup().addTo(this.map);
        
        // Add scale control
        L.control.scale().addTo(this.map);
    }

    clearMarkers() {
        this.airportLayer.clearLayers();
        this.markers.clear();
    }

    addAirport(airport) {
        if (!airport.latitude_deg || !airport.longitude_deg) {
            return; // Skip airports without coordinates
        }

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

        // Add AIP entries section
        if (aipEntries && aipEntries.length > 0) {
            html += `
                <div class="airport-detail-section">
                    <h6><i class="fas fa-file-alt"></i> AIP Data (${aipEntries.length})</h6>
            `;
            
            // Group by section
            const entriesBySection = {};
            aipEntries.forEach(entry => {
                const section = entry.section || 'Unknown';
                if (!entriesBySection[section]) {
                    entriesBySection[section] = [];
                }
                entriesBySection[section].push(entry);
            });
            
            Object.entries(entriesBySection).forEach(([section, entries]) => {
                html += `<h6 class="mt-2">${section.charAt(0).toUpperCase() + section.slice(1)}</h6>`;
                entries.forEach(entry => {
                    const fieldName = entry.std_field || entry.field;
                    html += `
                        <div class="aip-entry">
                            <strong>${fieldName}:</strong> ${entry.value}
                            ${entry.alt_value ? `<br><em>${entry.alt_value}</em>` : ''}
                        </div>
                    `;
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
        this.map.setView([lat, lng], zoom);
    }

    // Filter markers based on criteria
    filterMarkers(filters) {
        this.markers.forEach((marker, icao) => {
            // This will be implemented when we have the full airport data
            // For now, just show all markers
            marker.addTo(this.airportLayer);
        });
    }
}

// Create global map instance
let airportMap; 