#import <Foundation/Foundation.h>
#import <PDFKit/PDFKit.h>
#import <CoreGraphics/CoreGraphics.h>
#import <ImageIO/ImageIO.h>

static void renderPageToPNG(PDFPage *page, NSString *outPath, int maxDim) {
    if (!page || !outPath) return;
    NSRect bounds = [page boundsForBox:kPDFDisplayBoxMediaBox];
    CGFloat w = bounds.size.width;
    CGFloat h = bounds.size.height;
    if (w <= 0.0 || h <= 0.0) return;

    CGFloat scale = (CGFloat)maxDim / MAX(w, h);
    size_t pixelW = (size_t)(w * scale);
    size_t pixelH = (size_t)(h * scale);
    if (pixelW == 0) pixelW = 1;
    if (pixelH == 0) pixelH = 1;

    CGColorSpaceRef cs = CGColorSpaceCreateDeviceRGB();
    CGContextRef ctx = CGBitmapContextCreate(NULL, pixelW, pixelH, 8, pixelW * 4, cs, (CGBitmapInfo)kCGImageAlphaPremultipliedLast);
    CGColorSpaceRelease(cs);
    if (!ctx) return;

    CGContextSetInterpolationQuality(ctx, kCGInterpolationHigh);
    CGContextSetRGBFillColor(ctx, 1.0, 1.0, 1.0, 1.0);
    CGContextFillRect(ctx, CGRectMake(0, 0, pixelW, pixelH));

    CGContextScaleCTM(ctx, scale, scale);
    [page drawWithBox:kPDFDisplayBoxMediaBox toContext:ctx];

    CGImageRef cgImage = CGBitmapContextCreateImage(ctx);
    CGContextRelease(ctx);
    if (!cgImage) return;

    CFURLRef outURL = (__bridge CFURLRef)[NSURL fileURLWithPath:outPath];
    CGImageDestinationRef dest = CGImageDestinationCreateWithURL(outURL, (CFStringRef)@"public.png", 1, NULL);
    if (dest) {
        CGImageDestinationAddImage(dest, cgImage, NULL);
        CGImageDestinationFinalize(dest);
        CFRelease(dest);
    }
    CGImageRelease(cgImage);
}

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        if (argc < 2) return 1;
        NSString *pdfPath = [NSString stringWithUTF8String:argv[1]];
        NSURL *url = [NSURL fileURLWithPath:pdfPath];
        PDFDocument *doc = [[PDFDocument alloc] initWithURL:url];
        if (!doc || doc.pageCount == 0) return 2;

        NSInteger totalPages = doc.pageCount;
        if (argc < 4) {
            printf("%ld\n", (long)totalPages);
            return 0;
        }

        int targetPage = atoi(argv[2]);
        NSString *outPath = [NSString stringWithUTF8String:argv[3]];
        int maxDim = (argc >= 5) ? atoi(argv[4]) : 800;

        if (targetPage >= 1 && targetPage <= totalPages) {
            renderPageToPNG([doc pageAtIndex:(targetPage - 1)], outPath, maxDim);
        }

        // Optionale Zusatzseiten im selben Prozess vorrendern (seitenweises Vorabladen)
        for (int i = 5; i + 1 < argc; i += 2) {
            int extraPage = atoi(argv[i]);
            NSString *extraOut = [NSString stringWithUTF8String:argv[i + 1]];
            if (extraPage >= 1 && extraPage <= totalPages) {
                renderPageToPNG([doc pageAtIndex:(extraPage - 1)], extraOut, maxDim);
            }
        }

        printf("%ld\n", (long)totalPages);
        return 0;
    }
}
