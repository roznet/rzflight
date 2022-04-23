//
//  File.swift
//  
//
//  Created by Brice Rosenzweig on 23/04/2022.
//

import Foundation

#if os(iOS)
import UIKit

extension Heading.Direction {
    var image : UIImage? {
        switch self {
        case .left:
            return UIImage(systemName: "arrow.left")
        case .right:
            return UIImage(systemName: "arrow.right")
        case .behind:
            return UIImage(systemName: "arrow.up")
        case .ahead:
            return UIImage(systemName: "arrow.down")
        }
    }
}


#endif
