//
//  Log.swift
//  MentalCrosswind
//
//  Created by Brice Rosenzweig on 07/03/2022.
//

import Foundation
import OSLog

extension Logger {
    public static let web = Logger(subsystem: Bundle.main.bundleIdentifier!, category: "web")
}
