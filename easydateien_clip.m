#import <AppKit/AppKit.h>
#import <Foundation/Foundation.h>
#import <ImageIO/ImageIO.h>

// Maximale Kantenlänge der als Bilddaten in die Zwischenablage gelegten Vorschau.
// Die Quelldatei wird dabei nie verändert — nur die eingebettete PNG-/TIFF-Kopie
// wird auf diese Größe begrenzt (wie im Finder üblich). Damit lassen sich auch
// große HEIC-/RAW-Aufnahmen schnell und speicherarm kopieren, statt die Pixel in
// voller Auflösung zu laden und doppelt (PNG + TIFF) zu encodieren.
static const NSInteger kMaxClipboardPixelSize = 2048;

// Erkennt gängige Bilddateitypen, für die eine eingebettete Bildvorschau beigelegt wird.
static BOOL easeIsImagePath(NSString *path) {
    NSString *ext = [[path pathExtension] lowercaseString];
    if ([ext isEqualToString:@"png"] || [ext isEqualToString:@"jpg"] ||
        [ext isEqualToString:@"jpeg"] || [ext isEqualToString:@"gif"] ||
        [ext isEqualToString:@"tiff"] || [ext isEqualToString:@"tif"] ||
        [ext isEqualToString:@"webp"] || [ext isEqualToString:@"heic"] ||
        [ext isEqualToString:@"heif"] || [ext isEqualToString:@"bmp"] ||
        [ext isEqualToString:@"avif"] || [ext isEqualToString:@"raw"]) {
        return YES;
    }
    return NO;
}

// Dekodiert ein Bild speicherschonend für die Zwischenablage. Bei Bildern, deren
// längste Kante kMaxClipboardPixelSize übersteigt, erzeugt ImageIO direkt ein
// herunterskaliertes Thumbnail — die volle Pixelgröße wird nie ausdekodiert.
// Der Aufrufer muss das Ergebnis mit CGImageRelease freigeben (NULL bei Fehler).
static CGImageRef easeScaledImageForPath(NSString *path) {
    if (!path || ![[NSFileManager defaultManager] fileExistsAtPath:path]) {
        return NULL;
    }
    NSURL *url = [NSURL fileURLWithPath:path];
    CGImageSourceRef source = CGImageSourceCreateWithURL((__bridge CFURLRef)url, NULL);
    if (!source) {
        return NULL;
    }
    NSDictionary *options = @{
        (id)kCGImageSourceCreateThumbnailFromImageAlways : @YES,
        (id)kCGImageSourceCreateThumbnailWithTransform : @YES,
        (id)kCGImageSourceThumbnailMaxPixelSize : @(kMaxClipboardPixelSize),
    };
    CGImageRef image = CGImageSourceCreateThumbnailAtIndex(source, 0, (__bridge CFDictionaryRef)options);
    CFRelease(source);
    return image;
}

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        if (argc < 2) return 1;
        NSString *action = [NSString stringWithUTF8String:argv[1]];
        NSPasteboard *pb = [NSPasteboard generalPasteboard];

        if ([action isEqualToString:@"set"] && argc > 2) {
            [pb clearContents];

            NSMutableArray<NSString *> *paths = [NSMutableArray array];
            for (int i = 2; i < argc; i++) {
                NSString *p = [NSString stringWithUTF8String:argv[i]];
                [paths addObject:p];
            }

            NSMutableArray<NSPasteboardType> *types = [NSMutableArray arrayWithObjects:
                (NSPasteboardType)@"NSFilenamesPboardType",
                NSPasteboardTypeFileURL,
                NSPasteboardTypeString,
                nil
            ];

            NSData *pngData = nil;
            NSData *tiffData = nil;
            // Bilddaten werden nur bei genau einer ausgewählten Bilddatei beigelegt
            // (gleiche Regel wie zuvor, damit Mehrfachauswahlen unverändert bleiben).
            if ([paths count] == 1 && easeIsImagePath(paths[0])) {
                CGImageRef cgRef = easeScaledImageForPath(paths[0]);
                if (cgRef) {
                    NSBitmapImageRep *rep = [[NSBitmapImageRep alloc] initWithCGImage:cgRef];
                    pngData = [rep representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
                    tiffData = [rep representationUsingType:NSBitmapImageFileTypeTIFF properties:@{}];
                    if (pngData) [types addObject:NSPasteboardTypePNG];
                    if (tiffData) [types addObject:NSPasteboardTypeTIFF];
                    CGImageRelease(cgRef);
                }
            }

            [pb declareTypes:types owner:nil];
            [pb setPropertyList:paths forType:(NSPasteboardType)@"NSFilenamesPboardType"];

            if ([paths count] > 0) {
                NSURL *firstUrl = [NSURL fileURLWithPath:paths[0]];
                if (firstUrl) {
                    [pb setString:[firstUrl absoluteString] forType:NSPasteboardTypeFileURL];
                }
            }

            if ([paths count] > 0) {
                NSString *allPaths = [paths componentsJoinedByString:@"\n"];
                [pb setString:allPaths forType:NSPasteboardTypeString];
            }

            if (pngData) {
                [pb setData:pngData forType:NSPasteboardTypePNG];
            }
            if (tiffData) {
                [pb setData:tiffData forType:NSPasteboardTypeTIFF];
            }

            return 0;
        } else if ([action isEqualToString:@"get"]) {
            id filenames = [pb propertyListForType:(NSPasteboardType)@"NSFilenamesPboardType"];
            if ([filenames isKindOfClass:[NSArray class]] && [filenames count] > 0) {
                for (NSString *p in filenames) {
                    if ([p length] > 0) printf("%s\n", [p UTF8String]);
                }
                return 0;
            }

            NSArray *classes = @[[NSURL class]];
            NSDictionary *options = @{NSPasteboardURLReadingFileURLsOnlyKey: @YES};
            NSArray *urls = [pb readObjectsForClasses:classes options:options];
            if (urls && [urls count] > 0) {
                for (NSURL *url in urls) {
                    printf("%s\n", [[url path] UTF8String]);
                }
                return 0;
            }

            NSString *str = [pb stringForType:NSPasteboardTypeString];
            if (str && [str length] > 0) {
                printf("%s\n", [str UTF8String]);
            }
            return 0;
        }
    }
    return 0;
}
